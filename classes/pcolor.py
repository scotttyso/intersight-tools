import io, os, re, shutil, sys, textwrap

_ANSI_ESCAPE = re.compile(r'\033\[[0-9;]*m')
_log_file    = None  # set by init_log(); None means no file logging


class TeeStream(io.TextIOBase):
    """Wraps an existing stream, mirroring writes to a log file (ANSI-stripped)."""
    def __init__(self, original, log_path):
        self._original = original
        self._log      = open(log_path, 'a', encoding='utf-8', buffering=1)

    def write(self, text):
        self._original.write(text)
        self._log.write(_ANSI_ESCAPE.sub('', text))
        return len(text)

    def flush(self):
        self._original.flush()
        self._log.flush()

    def fileno(self):  # keep isatty() working correctly
        return self._original.fileno()

    def isatty(self):
        return False


def init_log(log_path):
    """Redirect sys.stdout through TeeStream so all print() and pcolor output
    is mirrored to *log_path* (with ANSI codes stripped)."""
    global _log_file
    _log_file  = log_path
    sys.stdout = TeeStream(sys.stdout, log_path)


#=============================================================================
# Functions: Print in Color
#=============================================================================
def print_process(cchar, ptext):
    def terminal_width():
        # Leave margin so terminal-level hard wrapping does not break indentation.
        columns = shutil.get_terminal_size(fallback=(108, 24)).columns
        return max(50, columns - 10)

    def color_line(text):
        return f"\033[{cchar}{text}\033[00m"

    def print_wrapped(text, subsequent_indent=''):
        wrapped = textwrap.fill(
            text,
            width=terminal_width(),
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=False,
            break_on_hyphens=False,
            subsequent_indent=subsequent_indent,
        )
        for line in wrapped.splitlines():
            print(color_line(line))

    if type(ptext) == dict or type(ptext) == list: print(color_line(ptext))
    elif re.search(r'^\[|\{', ptext): print(color_line(ptext))
    elif re.search(r'^\n[\+\-\*]', ptext): print(color_line(ptext))
    elif re.search(r'^$', ptext): print(color_line(ptext))
    elif re.search(r'^[ ]+[\*|\-]([ ]+)?[a-zA-Z0-9`]', ptext):
        indent = len(re.search(r'^([ ]+[\*|\-]([ ]+)?)[a-zA-Z0-9`]', ptext).group(1))
        sub_indent = ' ' * indent
        print_wrapped(ptext, subsequent_indent=sub_indent)
    elif re.search(r'^[ ]+[0-9]+\.([ ]+)?[a-zA-Z0-9`]', ptext):
        indent = len(re.search(r'^([ ]+[0-9]+\.([ ]+)?)[a-zA-Z0-9`]', ptext).group(1))
        sub_indent = ' ' * indent
        print_wrapped(ptext, subsequent_indent=sub_indent)
    elif re.search(r'^[\*|\-]([ ]+)?[a-zA-Z0-9`]', ptext):
        indent = len(re.search(r'(^[\*|\-]([ ]+)?)[a-zA-Z0-9`]', ptext).group(1))
        sub_indent = ' ' * indent
        print_wrapped(ptext, subsequent_indent=sub_indent)
    elif re.search(r'^[ ]+[a-zA-Z0-9`\!]', ptext):
        indent = len(re.search(r'^([ ]+)[a-zA-Z0-9`\!]', ptext).group(1))
        sub_indent = ' ' * indent
        print_wrapped(ptext, subsequent_indent=sub_indent)
    elif re.search(r'^[a-zA-Z0-9\-\=\!]', ptext):
        print_wrapped(ptext)
    else:
        print_wrapped(ptext)
        #print('ERROR with PCOLOR, didnt match regex') 
        #print(f'value `{ptext}`')
        #print(re.search(r'^([.\r\n]*)$', ptext).group(1))
        #exit()

def Black(ptext):      cchar = '98m'; print_process(cchar, ptext)
def Cyan(ptext):       cchar = '96m'; print_process(cchar, ptext)
def Green(ptext):      cchar = '92m'; print_process(cchar, ptext)
def Red(ptext):        cchar = '91m'; print_process(cchar, ptext)
def LightGray(ptext):  cchar = '97m'; print_process(cchar, ptext)
def LightPurple(ptext):cchar = '94m'; print_process(cchar, ptext)
def Purple(ptext):     cchar = '95m'; print_process(cchar, ptext)
def Yellow(ptext):     cchar = '93m'; print_process(cchar, ptext)
