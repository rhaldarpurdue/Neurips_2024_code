Command for ADAM clean training:
python -u convergence.py --data ${D} --seed ${SEED} --epochs 1000

Command for clean training with batch normalization:
python -u convergence_bn.py --data ${D} --seed ${SEED} --epochs 1000

Command for clean training with second-order optimization using KFAC:
python -u mnist_kfac.py --data ${D} --seed ${SEED} --epochs 1000

Arguments: ${D}="MNIST" or "FashionMNIST"
