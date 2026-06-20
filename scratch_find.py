txt = open('core/tui.py', encoding='utf-8').read()
for i, l in enumerate(txt.splitlines()):
    if 'update(' in l and '""' in l or "''" in l:
        print(f'{i+1}: {l}')
