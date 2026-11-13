#!/bin/bash
# Runs inside the container: /data writable, /files read-only.
set -e
cd /data
for n in full numeric low; do
  /opt/plink/plink --file $n --a1-allele /files/DN_SNPS/dummy.bim 5 2 --make-bed --out $n > /dev/null
  echo "made $n"
done
# Same genotypes but PLINK-default A1 (= minor allele in this sample set)
/opt/plink/plink --file full --make-bed --out full_minorA1 > /dev/null
rm -f *.ped *.map *.log *.nosex
echo "SNPs whose A1 differs between full and full_minorA1:"
awk 'NR==FNR{a[$2]=$5;next} a[$2]!=$5' full.bim full_minorA1.bim | wc -l
