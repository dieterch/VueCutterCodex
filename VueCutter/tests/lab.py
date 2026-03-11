

# if inplace:
#     nexc_lst = ["self._mcut_binary","-r","-n",f"'{movie.title}'","-d", f"'{movie.summary}'",f"{self._pathname(movie)}","-c"]
# else:
#     nexc_lst = ["self._mcut_binary","-n",f"'{movie.title}'","-d", f"'{movie.summary}'",f"{self._pathname(movie)}","-c"]

# for cut in cutlist:
#     for key, value in cut.items():
#             nexc_lst.append(value)

cutlist = [{'t0': '00:00:00', 't1': '00:32:22'}, {'t0': '00:37:38', 't1': '00:55:58'}]
cutlist = [{'t0': '00:16:08', 't1': '01:44:08'}]
nexc_lst = ['a','b','c','d','e','f','g']
nexc_lst += [v for c in cutlist for k,v in c.items()]
print(nexc_lst)
inplace = True
if inplace:
    nexc_lst.insert(1,'-r')
print(nexc_lst)