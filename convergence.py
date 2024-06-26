from data_utils import *
import torch
import numpy as np
import random
from utils import *
import argparse
import logging
import time
import math
#import torchattacks
import os




parser = argparse.ArgumentParser()
parser.add_argument("--epochs", type=int, default=10, help="total epochs")
parser.add_argument("--seed", type=int, default=1, help="seed for run")
parser.add_argument("--bs",type=int, default=256, help="batch size")
parser.add_argument("--lr",type=float, default=1e-3, help="learning rate")
parser.add_argument("--pad",type=int, default=0, help="padding")
parser.add_argument("--data",type=str, default='MNIST', help="data_name")
parser.add_argument("--log",type=int, default=10, help="computing robust accuracies at uniform interval")
arg = parser.parse_args()
print(arg)

seed=arg.seed
torch.manual_seed(seed)
random.seed(seed)
np.random.seed(seed)

data_name=arg.data
data_train,data_test=DATA(data_name)

train_loader = torch.utils.data.DataLoader(data_train, batch_size=arg.bs, shuffle=True) 
test_loader = torch.utils.data.DataLoader(data_test, batch_size=arg.bs, shuffle=False)

class Flatten(nn.Module):
    def forward(self, x):
        return x.view(x.size(0), -1)
    
class mnist_CNN(nn.Module):
    def __init__(self,pad=0,n_classes=10,cost=10):
        super().__init__()
        c=math.floor(pad/2)
        self.rep = nn.Sequential(
            nn.Conv2d(1, 16, 4, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 32, 4, stride=2, padding=1),
            nn.ReLU(),
            Flatten(),
            nn.Linear(32*(7+c)*(7+c),100),
            nn.ReLU())
        self.last=nn.Linear(100, 10)
        self.cost=cost
    def forward(self, x):
        return self.last(self.rep(x))
    def contrast_loss(self,x,y):
        cache=self.rep(x)
        d2=torch.cdist(cache,cache,p=2)
        d0=-torch.cdist(y.float().unsqueeze(1),y.float().unsqueeze(1),p=0)
        d0=d0+(d0+1)
        d0=self.cost*d0
        return torch.mean(torch.clamp(d2*d0,-1000,None))

def robust_train(lr_max,epochs,loader,attack='none',epsilon=0.3,alpha=2/255,trim=True,CL=False):
    RA={0.05:[],0.1:[],0.2:[],0.3:[]}
    RL={0.05:[],0.1:[],0.2:[],0.3:[]}
    CA=[]
    Closs=[]
    TrA=[]
    TrL=[]
    attack_iters=int((epsilon/alpha)*1.2)
    model=mnist_CNN(pad=arg.pad).cuda()
    model.train()
    criterion = nn.CrossEntropyLoss()
    opt = torch.optim.Adam(model.parameters(), lr=lr_max)
    logger.info('Epoch \t Time \t LR \t \t Train Loss \t Train Acc')
    for epoch in range(epochs):

        start_time = time.time()
        train_loss = 0
        train_acc = 0
        train_n = 0
        #linf = torchattacks.PGD(model, eps=epsilon, alpha=alpha, steps=attack_iters, random_start=True)
        for i, (X, y) in enumerate(loader):
            X, y = X.cuda(), y.cuda()
            X=X.float()
            #X=T.Pad(padding=pad,fill=fill)(X) # adding borders
            if attack == 'fgsm':
                delta=attack_fgsm(model, X, y, epsilon,trim)
            elif attack == 'none' :#or epoch<3:
                delta = torch.zeros_like(X)
            elif attack == 'pgd':#and epoch>=3:
                delta=attack_pgd_linf(model, X, y, epsilon, alpha, attack_iters,1,trim)
                #delta=attack_pgd(model, X, y, epsilon, alpha, attack_iters,1,True)
                #xadv=linf(X,y)
                #delta=xadv-X
            if trim:
                output = model(torch.clamp(X + delta, 0, 1))
            else:
                output = model(X + delta)
            
            if CL:
                loss = criterion(output, y) + model.contrast_loss(X, y)
            else:
                loss = criterion(output, y)
            opt.zero_grad()
            loss.backward()
            opt.step()

            train_loss += loss.item() * y.size(0)
            train_acc += (output.max(1)[1] == y).sum().item()
            train_n += y.size(0)
        #if train_acc/train_n>0.90: #and epoch>3: #early stopping for adv loss fmnist 0.5000 epochs >5 total
         #   break

        train_time = time.time()
        logger.info('%d \t %.1f \t %.4f \t %.4f \t %.4f',epoch, train_time - start_time, lr_max, train_loss/train_n, train_acc/train_n)
        TrA.append(train_acc/train_n)
        TrL.append(train_loss/train_n)
        if (epoch+1)%arg.log==0:
            for eps in 0.05,0.1,0.2,0.3:
                _,rob_acc,rob_loss=classwise_acc(model,test_loader,trim=True,attack='linf',epsilon=eps)
                RA[eps].append(rob_acc)
                RL[eps].append(rob_loss)
            _,clean_acc,clean_loss=classwise_acc(model,test_loader,trim=True,attack='none',epsilon=eps)
            CA.append(clean_acc)
            Closs.append(clean_loss)
    return model,RA,RL,CA,CL,TrA,TrL

def classwise_acc(model,loader,epsilon=0.3,step_size=2/255,attack='linf',trim=True,label=False,return_data=False):
    model.eval()
    attack_iters=int((epsilon/step_size)*1.2)
    acc=0
    n=0
    #rob_lst=[]
    class_acc=[0]*10
    class_n=[0]*10
    advloss=0
    if return_data:
        x_adv,y_adv=[],[]
    for i, (X, y) in enumerate(loader):
        X, y = X.float().cuda(), y.cuda()
        #X=T.Pad(padding=pad,fill=fill)(X) # adding borders
        robust=torch.zeros(X.shape[0])
        if attack=='linf':
            #delta=attack_fgsm(model, X, y, epsilon,True)
            if label:
                delta=attack_pgd_linf(model, X, y, epsilon, step_size, attack_iters,1,trim,label=True)
            else:
                delta=attack_pgd_linf(model, X, y, epsilon, step_size, attack_iters,1,trim,label=False)
        elif attack=='l2':
            delta=attack_pgd_l2(model, X, y, epsilon, step_size, attack_iters,1,trim)
        elif attack=='none':
            delta=delta = torch.zeros_like(X)
        if not label:
            output = model(torch.clamp(X + delta, 0, 1))
        else:
            output = model(X + delta,y)
        if return_data:
            x_adv.append(X+delta)
            y_adv.append(y)
        advloss+=F.cross_entropy(output,y,reduction='sum').item()
        I = output.max(1)[1] == y # index which were not fooled
        robust[I]=1
        for j in range(10):
            cls_id=(y==j).cpu()
            class_acc[j]+=robust[cls_id].sum().item()
            class_n[j]+=cls_id.sum().item()
        acc += robust.sum().item()
        n += y.size(0)
        #rob_lst.append(robust)
    logger.info('Adv Loss \t Adv Acc')
    logger.info('%.4f \t %.4f', advloss/n, (acc)/n)
    class_acc = [class_acc[index]/value for index,value in enumerate(class_n)]
    if return_data:
        x_adv=torch.cat(x_adv)
        y_adv=torch.cat(y_adv)
        return class_acc, torch.utils.data.TensorDataset(x_adv,y_adv)
    else:
        return class_acc,acc/n, advloss/n

# main 
file_name=data_name+'_Clean-'+str(seed)+'.txt'
logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=file_name,
                filemode='w',
    format='[%(asctime)s] - %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S',
    level=logging.INFO)

mod,RA,RL,CA,CL,TrA,TrL=robust_train(lr_max=arg.lr,epochs=arg.epochs,loader=train_loader,attack="none",epsilon=0.3,trim=False)
res=[RA,RL,CA,CL,TrA,TrL]
#import pickle as pkl
#with open('mnist_conv.pkl', "wb") as f:
#    pkl.dump(res, f)