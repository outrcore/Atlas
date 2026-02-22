#!/usr/bin/expect -f
set timeout 300

spawn claude setup-token

# Wait for the URL to appear
expect {
    "Paste code here if prompted >" {
        # Ready for code input - wait indefinitely for user
        puts "\n\n=== SESSION READY FOR CODE ===\n"
        interact
    }
    timeout {
        puts "Timeout waiting for prompt"
        exit 1
    }
}
