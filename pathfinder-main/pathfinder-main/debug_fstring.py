
try:
    # Simulating what I suspect is happening (single braces)
    x = f'{"title": "Arts","description": "...","why_fit": "...","next_steps": "..."}'
    print(f"Result: {x}")
except Exception as e:
    print(f"Caught expected error: {e}")

print("-" * 20)

try:
    # Simulating what is in the file (double braces)
    x = f'{{"title": "Arts","description": "...","why_fit": "...","next_steps": "..."}}'
    print(f"Result: {x}")
except Exception as e:
    print(f"Caught unexpected error: {e}")
