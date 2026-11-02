import sys
def ed(path, old, new):
    s=open(path).read(); assert s.count(old)==1, (path, old[:60]); open(path,'w').write(s.replace(old,new))
