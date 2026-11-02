import io,re
p=r"sources\05-播客转写\audio_txt\FW8NPflTV7gt_眼哥股市会 1月26日._clean.txt"
t=io.open(p,encoding="utf-8",errors="ignore").read()
out=open(r"tools\_b37_dbg7.txt","w",encoding="utf-8")
out.write("len=%d\n"%len(t))
out.write("has xianqian: %s\n"%("闲钱" in t))
ts=re.findall(r"\[(\d\d:\d\d:\d\d)\]",t)
out.write("max ts=%s count=%d\n"%(max(ts),len(ts)))
out.write("tail:\n"+t[-500:])
out.close()
