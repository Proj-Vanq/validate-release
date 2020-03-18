#!/usr/bin/python3

import hashlib
import re
import sys
import zipfile

def Linux(z):
    yield from ()
def Mac(z):
    yield from ()
def Windows32(z):
    yield from ()
def Windows64(z):
    yield from ()
def Symbols(z):
    expected = {
        ('Linux', 'x86_64', 'daemon'),
        ('Linux', 'x86_64', 'daemonded'),
        ('Linux', 'x86_64', 'daemon-tty'),
        ('windows', 'x86', 'daemon.exe'),
        ('windows', 'x86', 'daemonded.exe'),
        ('windows', 'x86', 'daemon-tty.exe'),
        ('windows', 'x86_64', 'daemon.exe'),
        ('windows', 'x86_64', 'daemonded.exe'),
        ('windows', 'x86_64', 'daemon-tty.exe'),
        ('NaCl', 'x86', 'cgame'),
        ('NaCl', 'x86_64', 'cgame'),
        ('NaCl', 'x86', 'sgame'),
        ('NaCl', 'x86_64', 'sgame'),
    }
    for filename in z.namelist():
        if not filename.endswith('.sym'):
            continue
        m = re.fullmatch(r'symbols/([^/]+)/([0-9A-F]+)/([^/]+)\.sym', filename)
        if not m:
            yield 'Symbol filename %r does not match expected pattern' % filename
            continue
        f = z.open(filename)
        header = next(f).decode('ascii').split()
        if len(header) != 5 or header[0] != 'MODULE':
            yield 'Symbol file %r does not have a valid first line (module record)' % filename
            continue
        if m.group(2) != header[3]:
            yield 'Build ID in %r module line (%s) does not match that in the path (%s)' % (m.group(2), header[3])
        anything = False
        binary = header[4]
        if binary != m.group(1) or binary != m.group(3):
            yield 'Binary name inside %r (%s) does not match either the directory or filename' % (filename, binary)
        anything = False
        nacl_binary = None
        for line in f:
            # Arbitrarily chosen function that should appear in all binaries
            if b'tinyformat' in line:
                anything = True
            elif b'CG_Rocket_' in line:
                nacl_binary = 'cgame'
            elif b'G_admin_' in line:
                nacl_binary = 'sgame'
        if not anything:
            yield "Symbol file %r doesn't appear to actually have symbols (mistakenly used stripped binary?)" % filename
        platform = header[1]
        if binary == 'main.nexe':
            if not nacl_binary:
                continue # Can't identify binary
            platform = 'NaCl' # NaCl symbol files have "Linux" as the OS
            binary = nacl_binary
        triple = (platform, header[2], binary)
        if triple in expected:
            expected.remove(triple)
        else:
            yield 'Unexpected platform/arch/binary combination ' + str(triple)
    for missing in expected:
        yield 'No symbols found for ' + str(missing)

def CheckMd5sums(z, base, dpks):
    try:
        sums = z.open(base + 'md5sums')
    except KeyError:
        yield 'Missing md5sums file in pkg/'
        return
    dpks = set(dpks)
    for line in sums:
        md5, _, name = line.strip().decode('ascii').partition(' *')
        if not name:
            yield 'Bad line in md5sums: ' + repr(line)
            continue
        if name not in dpks:
            yield 'md5sums has file %r which does not exist in pkg/' % name
            continue
        dpks.remove(name)
        content = z.open(base + name).read()
        actual = hashlib.md5(content).digest().hex()
        if md5 != actual:
            yield 'md5sums says hash of %s is %s, but actual is %s' % (name, md5, actual)
    for unmatched in dpks:
        yield 'Missing md5sums entry for file: ' + unmatched

def CheckPkg(z, base):
    base += 'pkg/'
    dpks = []
    for name in z.namelist():
        if not name.startswith(base) or name == base:
            continue
        name = name[len(base):]
        if re.fullmatch(r'[^/]+\.dpk', name):
            dpks.append(name)
        elif name != 'md5sums':
            yield 'Unexpected filename in pkg/ ' + repr(name)
    unvanquished = base.split('/')[0] + '.dpk'
    if unvanquished not in dpks:
        yield 'Expected there to be a package named ' + unvanquished
    yield from CheckMd5sums(z, base, dpks)
    # TODO: Check DEPS files inside dpks?

def CheckRelease(filename, number):
    z = zipfile.ZipFile(filename)
    base = 'unvanquished_' + number + '/'
    for name, checker in (
        ('linux-amd64', Linux),
        ('macos-amd64', Mac),
        ('windows-i686', Windows32),
        ('windows-amd64', Windows64),
        ('symbols_' + number, Symbols),
    ):
        name = base + name + '.zip'
        try:
            info = z.getinfo(name)
        except KeyError:
            yield 'Missing file: ' + name
        else:
            yield from checker(zipfile.ZipFile(z.open(info)))
    yield from CheckPkg(z, base)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('Sample usage: check_release.py some/path/unvanquished_1.2.3.zip 1.2.3')
    for error in CheckRelease(*sys.argv[1:]):
        print(error)
