import sys

from pygeodata.cli import cli

if __name__ == '__main__':
    cli(['browse', *sys.argv[1:]], prog_name='pygeodata')
