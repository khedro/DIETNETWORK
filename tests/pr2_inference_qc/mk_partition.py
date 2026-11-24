import sys, h5py, numpy as np
sys.argv=['x']; import partition_data as pdm
np.random.seed(23)
with h5py.File('/files/1KGP/1KGP_2322inds_24pops_230Ksnps.hdf5','r') as f:
    names=np.array(f['class_label_names']); labels=[names[int(i)] for i in f['class_labels']]
    samples=[s.decode() for s in f['samples']]; lab=[names[int(i)].decode() for i in f['class_labels']]
ib=pdm.balanced_split(labels,5)
np.savez('/files/1KGP/1KGP_2322inds_24pops_230Ksnps_parition.npz', folds_indexes=np.array(ib,dtype=object))
with open('/files/1KGP/1000G.2322samples.labels.txt','w') as o:
    o.write('sample\tlabel\n'); [o.write(f'{s}\t{l}\n') for s,l in zip(samples,lab)]
print([len(x[2]) for x in ib])
