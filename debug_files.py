import os

print("--- FILE STRUCTURE DIAGNOSTIC ---")
start_path = os.path.join(os.path.dirname(__file__), 'src')

if not os.path.exists(start_path):
    print(f"❌ CRITICAL: The 'src' folder does not exist at: {start_path}")
else:
    print(f"✅ Found 'src' folder at: {start_path}")
    print("Listing contents:")
    for root, dirs, files in os.walk(start_path):
        level = root.replace(start_path, '').count(os.sep)
        indent = ' ' * 4 * (level)
        print(f"{indent}{os.path.basename(root)}/")
        for f in files:
            if f.endswith('.py'):
                print(f"{indent}    {f}")

print("---------------------------------")