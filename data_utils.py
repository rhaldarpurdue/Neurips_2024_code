# -*- coding: utf-8 -*-
"""
Created on Mon Oct  9 12:46:54 2023

@author: rajde
"""
import torch
import numpy as np
import matplotlib.pyplot as plt
from torchvision import datasets, transforms
from torchvision.utils import make_grid
import torchvision.transforms.functional as F_vis

def DATA(data_name):
    data_loc="../"+data_name+"-data"
    data_train = eval('datasets.{}(data_loc, train=True, download=True, transform=transforms.ToTensor())'.format(data_name))
    data_test = eval('datasets.{}(data_loc, train=False, download=True, transform=transforms.ToTensor())'.format(data_name))
    return data_train, data_test

def Classwise_DATA(data):
    # input: type(torchvision.datasets)
    sample_size=len(data)
    loader=torch.utils.data.DataLoader(data, batch_size=sample_size, shuffle=False)
    for x,y in loader:
        break
    n_class=len(torch.unique(y))
    X,Y=[None]*n_class,[None]*n_class
    for i in range(n_class):
        X[i]=x[y==i]
        Y[i]=y[y==i]
    return [torch.utils.data.TensorDataset(X[i],Y[i]) for i in range(n_class)]

def show(imgs):
    if not isinstance(imgs, list):
        imgs = [imgs]
    fig, axs = plt.subplots(ncols=len(imgs), squeeze=False)
    for i, img in enumerate(imgs):
        img = img.detach()
        img = F_vis.to_pil_image(img)
        axs[0, i].imshow(np.asarray(img))
        axs[0, i].set(xticklabels=[], yticklabels=[], xticks=[], yticks=[])

def plt_images(x):
    # input Type (Tensor)
    show(make_grid(x))