#!/usr/bin/env python3
"""
Validation Gate Pattern - Pipeline for validating agent outputs before execution.

Pattern: Draft Agent → Validator Agent → Human Approval → Execute

This module provides a validation pipeline that ensures high-stakes agent outputs
(code, emails, commands, configs) are validated before execution.

Usage:
    from validation_gate import ValidationPipeline, ValidationResult
    
    pipeline = ValidationPipeline(
        require_human_approval=True,
        validators=["syntax", "security", "style"]
    )
    
    result = pipeline.validate(
        content="code or text to validate",
        content_type="code",
        context={"language": "python"}
    )
    
    if result.approved:
        # Safe to execute
    else:
        print(result.issues)

Integration Notes for ATLAS:
    Use this BEFORE:
    - Sending emails (email_pipeline)
    - Making git commits to production repos (code_pipeline)
    - Running destructive commands (deploy_pipeline)
    - Posting to social media (email_pipeline)
    - Modifying config files (code_pipeline with content_type="config")
"""

import ast
import json
import os
import re
import uuid
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union
import yaml


# ============================================================================
# Constants
# ============================================================================

PENDING_APPROVALS_DIR = Path("/workspace/clawd/pending_approvals")

# Dangerous patterns for security validation
DANGEROUS_PATTERNS = {
    "shell": [
        (r"rm\s+-rf\s+[/~]", "Recursive delete from root or home directory"),
        (r"rm\s+-rf\s+\*", "Recursive delete with wildcard"),
        (r">\s*/dev/sd[a-z]", "Direct write to disk device"),
        (r"mkfs\.", "Filesystem format command"),
        (r"dd\s+if=.+of=/dev/", "Direct disk write with dd"),
        (r":\(\)\s*{\s*:\|:&\s*};:", "Fork bomb pattern"),
        (r"chmod\s+-R\s+777", "Overly permissive chmod"),
        (r"curl.*\|\s*(ba)?sh", "Pipe curl to shell (dangerous)"),
        (r"wget.*\|\s*(ba)?sh", "Pipe wget to shell (dangerous)"),
        (r"eval\s*\(.*\$", "Eval with variable interpolation"),
    ],
    "credentials": [
        (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][a-zA-Z0-9]{16,}", "Hardcoded API key"),
        (r"(?i)(password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{4,}", "Hardcoded password"),
        (r"(?i)(secret|token)\s*[=:]\s*['\"][a-zA-Z0-9]{16,}", "Hardcoded secret/token"),
        (r"(?i)bearer\s+[a-zA-Z0-9\-_]{20,}", "Hardcoded bearer token"),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", "Private key in code"),
        (r"(?i)aws[_-]?(access[_-]?key|secret)", "AWS credentials pattern"),
        (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API key pattern"),
        (r"ghp_[a-zA-Z0-9]{36}", "GitHub personal access token"),
        (r"xox[baprs]-[a-zA-Z0-9-]+", "Slack token pattern"),
    ],
    "sql_injection": [
        (r"f['\"].*SELECT.*{", "Potential SQL injection via f-string"),
        (r"['\"].*SELECT.*\+\s*\w+", "SQL string concatenation"),
        (r"execute\s*\(\s*f['\"]", "SQL execute with f-string"),
    ],
    "code_execution": [
        (r"exec\s*\(\s*[^)]*input", "Exec with user input"),
        (r"eval\s*\(\s*[^)]*input", "Eval with user input"),
        (r"__import__\s*\(", "Dynamic import (review carefully)"),
        (r"subprocess\..*shell\s*=\s*True", "Subprocess with shell=True"),
        (r"os\.system\s*\(", "os.system call (prefer subprocess)"),
    ],
}

# Email-specific dangerous patterns
EMAIL_PATTERNS = [
    (r"(?i)password.*attached", "Password mentioned with attachment reference"),
    (r"(?i)confidential.*forward", "Confidential info with forward request"),
    (r"(?i)(ssn|social\s+security)", "Social security number reference"),
    (r"(?i)credit\s+card.*\d{4}", "Credit card number pattern"),
]


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ValidationResult:
    """Result of validation pipeline execution."""
    
    approved: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validator_results: Dict[str, bool] = field(default_factory=dict)
    human_approval_required: bool = False
    human_approved: Optional[bool] = None
    approval_id: Optional[str] = None
    approval_prompt: Optional[str] = None
    content_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ValidationResult":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class PendingApproval:
    """A pending item waiting for human approval."""
    
    approval_id: str
    content: str
    content_type: str
    context: Dict[str, Any]
    validation_result: ValidationResult
    created_at: str
    expires_at: Optional[str] = None
    status: str = "pending"  # pending, approved, rejected, expired
    reviewer_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["validation_result"] = self.validation_result.to_dict()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingApproval":
        """Create from dictionary."""
        data["validation_result"] = ValidationResult.from_dict(data["validation_result"])
        return cls(**data)


# ============================================================================
# Validators
# ============================================================================

class BaseValidator:
    """Base class for validators."""
    
    name: str = "base"
    
    def validate(self, content: str, content_type: str, context: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        """
        Validate content.
        
        Returns:
            tuple: (passed, issues, warnings)
        """
        raise NotImplementedError


class SyntaxValidator(BaseValidator):
    """Validates syntax for code, JSON, YAML content."""
    
    name = "syntax"
    
    def validate(self, content: str, content_type: str, context: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        issues = []
        warnings = []
        
        language = context.get("language", "").lower()
        
        # Auto-detect language from content_type if not specified
        if not language and content_type == "config":
            if content.strip().startswith("{") or content.strip().startswith("["):
                language = "json"
            elif ":" in content and not content.strip().startswith("{"):
                language = "yaml"
        
        if content_type == "code" or language == "python":
            issues.extend(self._validate_python(content))
        
        if language == "json" or content_type == "config":
            json_issues = self._validate_json(content)
            if json_issues and language != "json":
                # It might be YAML, not JSON
                yaml_issues = self._validate_yaml(content)
                if not yaml_issues:
                    pass  # Valid YAML
                else:
                    issues.extend(json_issues)
            else:
                issues.extend(json_issues)
        
        if language == "yaml":
            issues.extend(self._validate_yaml(content))
        
        passed = len(issues) == 0
        return passed, issues, warnings
    
    def _validate_python(self, content: str) -> List[str]:
        """Check Python syntax."""
        issues = []
        try:
            ast.parse(content)
        except SyntaxError as e:
            issues.append(f"Python syntax error at line {e.lineno}: {e.msg}")
        return issues
    
    def _validate_json(self, content: str) -> List[str]:
        """Check JSON syntax."""
        issues = []
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            issues.append(f"JSON syntax error at line {e.lineno}: {e.msg}")
        return issues
    
    def _validate_yaml(self, content: str) -> List[str]:
        """Check YAML syntax."""
        issues = []
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            issues.append(f"YAML syntax error: {e}")
        return issues


class SecurityValidator(BaseValidator):
    """Validates content for security issues."""
    
    name = "security"
    
    def validate(self, content: str, content_type: str, context: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        issues = []
        warnings = []
        
        # Check for dangerous shell patterns
        if content_type in ("code", "command", "config"):
            for pattern, description in DANGEROUS_PATTERNS["shell"]:
                if re.search(pattern, content):
                    issues.append(f"[SECURITY] {description}")
        
        # Check for hardcoded credentials (all content types)
        for pattern, description in DANGEROUS_PATTERNS["credentials"]:
            if re.search(pattern, content):
                issues.append(f"[SECURITY] {description}")
        
        # Check code-specific patterns
        if content_type == "code":
            for pattern, description in DANGEROUS_PATTERNS["sql_injection"]:
                if re.search(pattern, content):
                    warnings.append(f"[SECURITY] {description}")
            
            for pattern, description in DANGEROUS_PATTERNS["code_execution"]:
                if re.search(pattern, content):
                    if "review carefully" in description.lower():
                        warnings.append(f"[SECURITY] {description}")
                    else:
                        issues.append(f"[SECURITY] {description}")
        
        # Check email-specific patterns
        if content_type == "email":
            for pattern, description in EMAIL_PATTERNS:
                if re.search(pattern, content):
                    warnings.append(f"[EMAIL] {description}")
        
        passed = len(issues) == 0
        return passed, issues, warnings


class StyleValidator(BaseValidator):
    """Basic style checks for code and text."""
    
    name = "style"
    
    def validate(self, content: str, content_type: str, context: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        issues = []
        warnings = []
        
        lines = content.split("\n")
        
        if content_type == "code":
            # Check line length
            for i, line in enumerate(lines, 1):
                if len(line) > 120:
                    warnings.append(f"Line {i} exceeds 120 characters ({len(line)} chars)")
            
            # Check for trailing whitespace
            trailing_ws_lines = [i for i, line in enumerate(lines, 1) if line.rstrip() != line]
            if trailing_ws_lines:
                warnings.append(f"Trailing whitespace on lines: {trailing_ws_lines[:5]}{'...' if len(trailing_ws_lines) > 5 else ''}")
            
            # Check for TODO/FIXME without context
            for i, line in enumerate(lines, 1):
                if re.search(r"#\s*(TODO|FIXME|XXX|HACK)\s*$", line):
                    warnings.append(f"Line {i}: TODO/FIXME without description")
            
            # Check for print statements (might be debug)
            print_lines = [i for i, line in enumerate(lines, 1) if re.search(r"^\s*print\s*\(", line)]
            if print_lines:
                warnings.append(f"Print statements found on lines: {print_lines[:5]} (debug code?)")
        
        if content_type == "email":
            # Check for subject line (first line convention)
            if lines and len(lines[0]) > 78:
                warnings.append("Subject line (first line) exceeds 78 characters")
            
            # Check for salutation
            if not any(re.match(r"^(Hi|Hello|Dear|Hey)", line) for line in lines[:3]):
                warnings.append("No salutation found in first 3 lines")
            
            # Check for sign-off
            if not any(re.search(r"(Regards|Thanks|Best|Cheers|Sincerely)", line) for line in lines[-5:]):
                warnings.append("No sign-off found in last 5 lines")
        
        # Style warnings don't fail validation
        passed = len(issues) == 0
        return passed, issues, warnings


class CustomValidator(BaseValidator):
    """Wrapper for custom validation functions."""
    
    def __init__(self, name: str, validate_fn: Callable):
        self.name = name
        self._validate_fn = validate_fn
    
    def validate(self, content: str, content_type: str, context: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        return self._validate_fn(content, content_type, context)


# Validator registry
VALIDATORS = {
    "syntax": SyntaxValidator(),
    "security": SecurityValidator(),
    "style": StyleValidator(),
}


# ============================================================================
# Validation Pipeline
# ============================================================================

class ValidationPipeline:
    """
    Pipeline for validating agent outputs before execution.
    
    Example:
        pipeline = ValidationPipeline(
            require_human_approval=True,
            validators=["syntax", "security", "style"]
        )
        
        result = pipeline.validate(
            content="print('hello world')",
            content_type="code",
            context={"language": "python"}
        )
    """
    
    def __init__(
        self,
        validators: Optional[List[Union[str, BaseValidator]]] = None,
        require_human_approval: bool = False,
        auto_approve_on_pass: bool = True,
        fail_fast: bool = False,
        custom_validators: Optional[List[BaseValidator]] = None,
    ):
        """
        Initialize validation pipeline.
        
        Args:
            validators: List of validator names or instances. Default: ["syntax", "security"]
            require_human_approval: Whether to require human approval even if validation passes
            auto_approve_on_pass: Auto-approve if all validators pass (and human approval not required)
            fail_fast: Stop on first validator failure
            custom_validators: Additional custom validator instances
        """
        self.require_human_approval = require_human_approval
        self.auto_approve_on_pass = auto_approve_on_pass
        self.fail_fast = fail_fast
        
        # Build validator list
        self._validators: List[BaseValidator] = []
        
        validator_list = validators or ["syntax", "security"]
        for v in validator_list:
            if isinstance(v, str):
                if v in VALIDATORS:
                    self._validators.append(VALIDATORS[v])
                else:
                    raise ValueError(f"Unknown validator: {v}")
            else:
                self._validators.append(v)
        
        if custom_validators:
            self._validators.extend(custom_validators)
    
    def validate(
        self,
        content: str,
        content_type: str = "code",
        context: Optional[Dict[str, Any]] = None,
        save_pending: bool = True,
    ) -> ValidationResult:
        """
        Validate content through the pipeline.
        
        Args:
            content: The content to validate
            content_type: Type of content ("code", "email", "message", "config", "command")
            context: Additional context (e.g., {"language": "python"})
            save_pending: Whether to save pending approval to disk
        
        Returns:
            ValidationResult with approval status and any issues/warnings
        """
        context = context or {}
        all_issues = []
        all_warnings = []
        validator_results = {}
        
        # Run all validators
        for validator in self._validators:
            passed, issues, warnings = validator.validate(content, content_type, context)
            validator_results[validator.name] = passed
            all_issues.extend(issues)
            all_warnings.extend(warnings)
            
            if self.fail_fast and not passed:
                break
        
        # Determine if approved
        all_passed = all(validator_results.values())
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Build result
        result = ValidationResult(
            approved=False,  # Will be set below
            issues=all_issues,
            warnings=all_warnings,
            validator_results=validator_results,
            human_approval_required=self.require_human_approval,
            human_approved=None,
            content_hash=content_hash,
        )
        
        # Determine approval status
        if not all_passed:
            result.approved = False
            result.approval_prompt = self._build_rejection_prompt(result, content, content_type)
        elif self.require_human_approval:
            result.approved = False
            result.approval_id = str(uuid.uuid4())[:8]
            result.approval_prompt = self._build_approval_prompt(result, content, content_type)
            
            if save_pending:
                self._save_pending_approval(content, content_type, context, result)
        else:
            result.approved = self.auto_approve_on_pass
        
        return result
    
    def _build_approval_prompt(self, result: ValidationResult, content: str, content_type: str) -> str:
        """Build prompt for human approval."""
        preview = content[:500] + "..." if len(content) > 500 else content
        
        prompt = f"""
🔒 VALIDATION GATE - Human Approval Required

**Content Type:** {content_type}
**Approval ID:** {result.approval_id}
**Hash:** {result.content_hash}

**Validator Results:**
{self._format_validator_results(result.validator_results)}

**Warnings:** {len(result.warnings)}
{chr(10).join(f"  ⚠️  {w}" for w in result.warnings[:5]) if result.warnings else "  None"}

**Content Preview:**
```
{preview}
```

To approve: `approve("{result.approval_id}")`
To reject: `reject("{result.approval_id}", reason="...")`
"""
        return prompt.strip()
    
    def _build_rejection_prompt(self, result: ValidationResult, content: str, content_type: str) -> str:
        """Build prompt explaining validation failure."""
        return f"""
❌ VALIDATION FAILED

**Content Type:** {content_type}
**Hash:** {result.content_hash}

**Issues Found:** {len(result.issues)}
{chr(10).join(f"  🚫 {i}" for i in result.issues)}

**Validator Results:**
{self._format_validator_results(result.validator_results)}

Content cannot be executed until issues are resolved.
"""
    
    def _format_validator_results(self, results: Dict[str, bool]) -> str:
        """Format validator results for display."""
        return "\n".join(
            f"  {'✅' if passed else '❌'} {name}"
            for name, passed in results.items()
        )
    
    def _save_pending_approval(
        self,
        content: str,
        content_type: str,
        context: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Save pending approval to disk."""
        PENDING_APPROVALS_DIR.mkdir(parents=True, exist_ok=True)
        
        pending = PendingApproval(
            approval_id=result.approval_id,
            content=content,
            content_type=content_type,
            context=context,
            validation_result=result,
            created_at=datetime.utcnow().isoformat(),
            status="pending",
        )
        
        filepath = PENDING_APPROVALS_DIR / f"{result.approval_id}.json"
        with open(filepath, "w") as f:
            json.dump(pending.to_dict(), f, indent=2)
    
    # ========================================================================
    # Pre-built pipelines
    # ========================================================================
    
    @classmethod
    def for_code(cls, language: str = "python") -> "ValidationPipeline":
        """
        Pre-built pipeline for code validation.
        
        Validators: syntax, security, style
        Human approval: No (auto-approve if passes)
        """
        return cls(
            validators=["syntax", "security", "style"],
            require_human_approval=False,
            auto_approve_on_pass=True,
        )
    
    @classmethod
    def for_email(cls) -> "ValidationPipeline":
        """
        Pre-built pipeline for email validation.
        
        Validators: security, style
        Human approval: Yes (always)
        """
        return cls(
            validators=["security", "style"],
            require_human_approval=True,
            auto_approve_on_pass=True,
        )
    
    @classmethod
    def for_deploy(cls) -> "ValidationPipeline":
        """
        Pre-built pipeline for deployment/destructive commands.
        
        Validators: security
        Human approval: Yes (always, no auto-approve)
        """
        return cls(
            validators=["security"],
            require_human_approval=True,
            auto_approve_on_pass=False,  # Must get explicit human approval
        )
    
    @classmethod
    def for_message(cls) -> "ValidationPipeline":
        """
        Pre-built pipeline for public messages (social media, etc).
        
        Validators: security, style
        Human approval: Yes
        """
        return cls(
            validators=["security", "style"],
            require_human_approval=True,
            auto_approve_on_pass=True,
        )
    
    @classmethod
    def for_config(cls) -> "ValidationPipeline":
        """
        Pre-built pipeline for configuration files.
        
        Validators: syntax, security
        Human approval: No
        """
        return cls(
            validators=["syntax", "security"],
            require_human_approval=False,
            auto_approve_on_pass=True,
        )


# ============================================================================
# Approval Management Functions
# ============================================================================

def list_pending() -> List[PendingApproval]:
    """List all pending approvals."""
    pending = []
    
    if not PENDING_APPROVALS_DIR.exists():
        return pending
    
    for filepath in PENDING_APPROVALS_DIR.glob("*.json"):
        try:
            with open(filepath) as f:
                data = json.load(f)
                approval = PendingApproval.from_dict(data)
                if approval.status == "pending":
                    pending.append(approval)
        except (json.JSONDecodeError, KeyError):
            continue
    
    return sorted(pending, key=lambda x: x.created_at, reverse=True)


def get_pending(approval_id: str) -> Optional[PendingApproval]:
    """Get a specific pending approval by ID."""
    filepath = PENDING_APPROVALS_DIR / f"{approval_id}.json"
    
    if not filepath.exists():
        return None
    
    with open(filepath) as f:
        data = json.load(f)
        return PendingApproval.from_dict(data)


def approve(approval_id: str, notes: Optional[str] = None) -> Optional[PendingApproval]:
    """
    Approve a pending item.
    
    Returns the updated PendingApproval, or None if not found.
    """
    filepath = PENDING_APPROVALS_DIR / f"{approval_id}.json"
    
    if not filepath.exists():
        return None
    
    with open(filepath) as f:
        data = json.load(f)
    
    data["status"] = "approved"
    data["reviewer_notes"] = notes
    data["validation_result"]["human_approved"] = True
    data["validation_result"]["approved"] = True
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    
    return PendingApproval.from_dict(data)


def reject(approval_id: str, reason: Optional[str] = None) -> Optional[PendingApproval]:
    """
    Reject a pending item.
    
    Returns the updated PendingApproval, or None if not found.
    """
    filepath = PENDING_APPROVALS_DIR / f"{approval_id}.json"
    
    if not filepath.exists():
        return None
    
    with open(filepath) as f:
        data = json.load(f)
    
    data["status"] = "rejected"
    data["reviewer_notes"] = reason
    data["validation_result"]["human_approved"] = False
    data["validation_result"]["approved"] = False
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    
    return PendingApproval.from_dict(data)


def clear_resolved(older_than_hours: int = 24) -> int:
    """
    Remove resolved (approved/rejected) approvals older than specified hours.
    
    Returns number of items cleared.
    """
    if not PENDING_APPROVALS_DIR.exists():
        return 0
    
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    cleared = 0
    
    for filepath in PENDING_APPROVALS_DIR.glob("*.json"):
        try:
            with open(filepath) as f:
                data = json.load(f)
            
            if data["status"] in ("approved", "rejected"):
                created = datetime.fromisoformat(data["created_at"])
                if created < cutoff:
                    filepath.unlink()
                    cleared += 1
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    
    return cleared


def pending_summary() -> str:
    """Get a summary of pending approvals for display."""
    pending = list_pending()
    
    if not pending:
        return "📭 No pending approvals"
    
    lines = [f"📬 **{len(pending)} Pending Approval(s)**\n"]
    
    for p in pending[:10]:  # Show max 10
        preview = p.content[:50].replace("\n", " ") + "..." if len(p.content) > 50 else p.content.replace("\n", " ")
        lines.append(
            f"• `{p.approval_id}` ({p.content_type}) - {preview}"
        )
    
    if len(pending) > 10:
        lines.append(f"\n... and {len(pending) - 10} more")
    
    return "\n".join(lines)


# ============================================================================
# CLI Interface (for testing)
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python validation_gate.py <command> [args]")
        print("\nCommands:")
        print("  list                    - List pending approvals")
        print("  approve <id> [notes]    - Approve a pending item")
        print("  reject <id> [reason]    - Reject a pending item")
        print("  clear [hours]           - Clear resolved items older than N hours")
        print("  test                    - Run test examples")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        print(pending_summary())
    
    elif command == "approve":
        if len(sys.argv) < 3:
            print("Usage: python validation_gate.py approve <id> [notes]")
            sys.exit(1)
        approval_id = sys.argv[2]
        notes = sys.argv[3] if len(sys.argv) > 3 else None
        result = approve(approval_id, notes)
        if result:
            print(f"✅ Approved: {approval_id}")
        else:
            print(f"❌ Not found: {approval_id}")
    
    elif command == "reject":
        if len(sys.argv) < 3:
            print("Usage: python validation_gate.py reject <id> [reason]")
            sys.exit(1)
        approval_id = sys.argv[2]
        reason = sys.argv[3] if len(sys.argv) > 3 else None
        result = reject(approval_id, reason)
        if result:
            print(f"❌ Rejected: {approval_id}")
        else:
            print(f"❌ Not found: {approval_id}")
    
    elif command == "clear":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        cleared = clear_resolved(hours)
        print(f"🧹 Cleared {cleared} resolved items")
    
    elif command == "test":
        print("=" * 60)
        print("Testing ValidationPipeline")
        print("=" * 60)
        
        # Test 1: Valid Python code
        print("\n📝 Test 1: Valid Python code")
        pipeline = ValidationPipeline.for_code()
        result = pipeline.validate(
            content='def hello():\n    print("Hello, world!")\n',
            content_type="code",
            context={"language": "python"}
        )
        print(f"  Approved: {result.approved}")
        print(f"  Issues: {result.issues}")
        
        # Test 2: Code with security issue
        print("\n🔒 Test 2: Code with hardcoded API key")
        result = pipeline.validate(
            content='API_KEY = "sk-1234567890abcdef1234567890abcdef"',
            content_type="code",
        )
        print(f"  Approved: {result.approved}")
        print(f"  Issues: {result.issues}")
        
        # Test 3: Dangerous command
        print("\n⚠️  Test 3: Dangerous shell command")
        deploy = ValidationPipeline.for_deploy()
        result = deploy.validate(
            content="rm -rf /important/data/*",
            content_type="command",
            save_pending=False
        )
        print(f"  Approved: {result.approved}")
        print(f"  Issues: {result.issues}")
        
        # Test 4: Email with approval required
        print("\n📧 Test 4: Email (requires approval)")
        email_pipe = ValidationPipeline.for_email()
        result = email_pipe.validate(
            content="Hi John,\n\nThanks for the meeting today.\n\nBest regards,\nAtlas",
            content_type="email",
            save_pending=False
        )
        print(f"  Approved: {result.approved}")
        print(f"  Human approval required: {result.human_approval_required}")
        print(f"  Warnings: {result.warnings}")
        
        print("\n" + "=" * 60)
        print("Tests complete!")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
