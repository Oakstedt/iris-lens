import os

# Define the path to the file based on your previous diagnostic
target_file = os.path.join("src", "NGPIris", "hcp", "hcp.py")

if os.path.exists(target_file):
    print(f"📖 Reading {target_file}...\n")
    with open(target_file, 'r') as f:
        lines = f.readlines()
        
    # Print lines defining the __init__ method
    printing = False
    for i, line in enumerate(lines):
        if "class HCPHandler" in line:
            print(f"Line {i}: {line.strip()}")
        if "def __init__" in line:
            printing = True
            print(f"Line {i}: {line.strip()}")
            # Print the next few lines in case arguments wrap
            for j in range(1, 10): 
                if i+j < len(lines):
                    next_line = lines[i+j].strip()
                    print(f"Line {i+j}: {next_line}")
                    if "):" in next_line or "pass" in next_line:
                        break
            break
else:
    print("❌ Could not find src/NGPIris/hcp/hcp.py")