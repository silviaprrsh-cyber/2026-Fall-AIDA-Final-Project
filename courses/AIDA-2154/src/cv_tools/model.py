"""Single shared CNN architecture for training and isolated inference."""
import torch
from torch import nn
from torch.nn import functional as F


class SmallSegCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.enc=nn.Sequential(nn.Conv2d(4,8,3,padding=1),nn.ReLU(),nn.Conv2d(8,8,3,padding=1),nn.ReLU())
        self.mid=nn.Sequential(nn.Conv2d(8,16,3,padding=1),nn.ReLU(),nn.Conv2d(16,16,3,padding=1),nn.ReLU())
        self.dec=nn.Sequential(nn.Conv2d(24,8,3,padding=1),nn.ReLU(),nn.Conv2d(8,1,1))
    def forward(self,x):
        e=self.enc(x);m=self.mid(F.max_pool2d(e,2));u=F.interpolate(m,size=e.shape[-2:],mode='bilinear',align_corners=False)
        return self.dec(torch.cat([e,u],dim=1)).squeeze(1)
