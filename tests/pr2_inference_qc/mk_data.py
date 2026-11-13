import h5py, numpy as np
rng = np.random.default_rng(0)
f = h5py.File('/files/1KGP/1KGP_2322inds_24pops_230Ksnps.hdf5', 'r')
bim = [l.split() for l in open('/files/DN_SNPS/dummy.bim')]
names = [s.decode() for s in f['snp_names']]
assert [b[1] + '_' + b[4] for b in bim] == names, 'bim/hdf5 SNP order or A1 mismatch'
samples = [s.decode() for s in f['samples']]
labs = [f['class_label_names'][int(i)].decode() for i in f['class_labels']]


def write(name, sidx, snp_idx, numeric=False):
    sidx = sorted(sidx)
    G = f['inputs'][sidx][:, snp_idx]
    with open(f'/data/{name}.map', 'w') as m:
        for j in snp_idx:
            b = bim[j]
            m.write(f'{b[0]}\t{b[1]}\t0\t{b[3]}\n')
    with open(f'/data/{name}.ped', 'w') as p, open(f'/data/{name}.truth', 'w') as t:
        for r, i in enumerate(sidx):
            iid = str(1000 + r) if numeric else samples[i]
            t.write(f'{iid}\t{labs[i]}\n')
            al = []
            for c, j in enumerate(snp_idx):
                ref, alt = bim[j][5], bim[j][4]
                al.append({0: f'{ref} {ref}', 1: f'{ref} {alt}', 2: f'{alt} {alt}', -1: '0 0'}[int(G[r, c])])
            p.write(f'{iid} {iid} 0 0 0 -9 ' + ' '.join(al) + '\n')


allsnp = np.arange(len(names))
pick = rng.choice(len(samples), 48, replace=False)
write('full', pick[:40], allsnp)
write('numeric', pick[40:48], allsnp, numeric=True)
write('low', pick[:8], np.sort(rng.choice(len(names), 300, replace=False)))
print('ok')
