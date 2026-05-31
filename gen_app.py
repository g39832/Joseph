"""Script to generate the new Phase 4 app.py."""
import os, shutil

SRC = r'C:\Users\Grayson\Desktop\Joseph\ui\app.py'
BAK = SRC + '.bak'

# Backup original
if not os.path.exists(BAK):
    shutil.copy2(SRC, BAK)
    print(f"Backed up to {BAK}")

lines = open(SRC, 'r', encoding='utf-8').readlines()
print(f"Original: {len(lines)} lines")

# We'll generate the new file as a list of lines
# by reading the original and transforming it, plus appending new methods

# Strategy: keep the imports and class definition, update COLORS->THEMES,
# replace key methods, and add new ones.

# For now let's just write a targeted transformation script

new_lines = []
skip_until = None
replacements = {}

for i, line in enumerate(lines):
    stripped = line.strip()
    
    # Replace COLORS dict with THEMES
    if stripped == 'COLORS = {':
        new_lines.append('''THEMES = {
    "dark": {
        "bg": "#141414", "panel": "#1e1e1e", "card": "#252525",
        "card_hover": "#2f2f2f", "card_user": "#2c2c2c",
        "border": "#333333", "border_light": "#404040",
        "accent": "#4d9de0", "accent_hover": "#3d8dd0", "accent_dim": "#2a5a8a",
        "text": "#ececec", "text_dim": "#7a7a7a", "text_muted": "#555555",
        "text_joseph": "#4d9de0", "text_user": "#d0d0d0",
        "success": "#3dba7a", "error": "#d95f5f", "warning": "#d4924a",
        "input_bg": "#1a1a1a", "scrollbar": "#333333", "thinking": "#8b5cf6", "sash": "#2a2a2a",
    },
    "light": {
        "bg": "#f5f5f5", "panel": "#ffffff", "card": "#ebebeb",
        "card_hover": "#e0e0e0", "card_user": "#e3f2fd",
        "border": "#d0d0d0", "border_light": "#bfbfbf",
        "accent": "#1976d2", "accent_hover": "#1565c0", "accent_dim": "#64b5f6",
        "text": "#1a1a1a", "text_dim": "#6a6a6a", "text_muted": "#9a9a9a",
        "text_joseph": "#1976d2", "text_user": "#1a1a1a",
        "success": "#2e7d32", "error": "#c62828", "warning": "#e65100",
        "input_bg": "#ffffff", "scrollbar": "#cccccc", "thinking": "#7c4dff", "sash": "#cccccc",
    },
}\n''')
        # Skip through the closing brace of COLORS
        # Find the closing brace
        depth = 1
        for j in range(i+1, len(lines)):
            if '}' in lines[j]:
                depth -= 1
                if depth == 0:
                    skip_until = j
                    break
            if '{' in lines[j]:
                depth += 1
        continue
    
    if skip_until is not None:
        if i <= skip_until:
            continue
        else:
            skip_until = None
    
    # COLORS. references -> self.colors.
    new_line = line.replace('COLORS[', 'self.colors[')
    new_line = new_line.replace('COLORS.', 'self.colors.')
    # FONTS stays the same
    
    new_lines.append(new_line)

with open(SRC, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print(f"Wrote {len(new_lines)} lines (transformed)")
