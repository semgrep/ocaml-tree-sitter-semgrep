# Semgrep ellipsis
...
cat ...
... --force

# Semgrep metavariables / all-caps shell variables
echo $FOO
$FOO

# Unambiguous semgrep metavariables (experimental)
echo ${{BAR}}
${{BAR}}
