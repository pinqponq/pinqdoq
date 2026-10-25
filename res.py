import re,sys
f,mode=sys.argv[1],sys.argv[2]
t=open(f).read()
def sub(m):
    o,th=m.group(1),m.group(2)
    if mode=="ours": return o
    if mode=="both": return o+th
    if mode=="theirs_plus_first_ours_line":
        first=o.split("\n")[0]+"\n"
        rest_has_scripts="scripts/        → NOT copied" in th
        return first+th+("" if rest_has_scripts else "".join(l+"\n" for l in o.split("\n")[1:] if l))
t2=re.sub(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n",sub,t,flags=re.S)
open(f,"w").write(t2); print(f,"conflicts left:",len(re.findall(r"^(<<<<<<<|>>>>>>>)",t2,re.M)))
