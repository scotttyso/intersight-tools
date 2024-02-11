import re, textwrap
wrap = textwrap.TextWrapper()
#=============================================================================
# Functions: Print in Color
#=============================================================================
def print_process(cchar, ptext):
    if len(ptext) <= 109: print(f"\033[{cchar} {ptext}\033[00m")
    elif re.search(r'^\n[\+\-]', ptext): print(f"\033[{cchar} {ptext}\033[00m")
    elif re.search(r'^$', ptext): print(f"\033[{cchar} {ptext}\033[00m")
    elif re.search(r'^\{', ptext): print(f"\033[{cchar} {ptext}\033[00m")
    elif re.search('^([ ]+)[\\*|\\-]([ ]+)?[a-zA-Z0-9]', ptext):
        indent = len(re.search('^([ ]+)[\\*|\\-]([ ]+)?', ptext).group(1))
        sub_indent = ' ' * (indent) + '   '
        print(textwrap.fill(f"\033[{cchar} {ptext}\033[00m", replace_whitespace=False, subsequent_indent=sub_indent, width=108))
    elif re.search('^[\\*|\\-] [a-zA-Z0-9]', ptext):
        sub_indent = ' ' * indent
        print(textwrap.fill(f"\033[{cchar} {ptext}\033[00m", replace_whitespace=False, subsequent_indent=sub_indent, width=108))
    elif re.search('^[a-zA-Z0-9\\-\\=]', ptext):
        print(textwrap.fill(f"\033[{cchar} {ptext}\033[00m", replace_whitespace=False, width=108))
    else:
        print('ERROR with PCOLOR, didnt match regex') 
        print(f'value `{ptext}`')
        print(re.search(r'^([.\r\n]*)$', ptext).group(1))
        exit()

def Black(ptext):      cchar = '98m'; print_process(cchar, ptext)
def Cyan(ptext):       cchar = '96m'; print_process(cchar, ptext)
def Green(ptext):      cchar = '92m'; print_process(cchar, ptext)
def Red(ptext):        cchar = '91m'; print_process(cchar, ptext)
def LightGray(ptext):  cchar = '97m'; print_process(cchar, ptext)
def LightPurple(ptext):cchar = '94m'; print_process(cchar, ptext)
def Purple(ptext):     cchar = '95m'; print_process(cchar, ptext)
def Yellow(ptext):     cchar = '93m'; print_process(cchar, ptext)
