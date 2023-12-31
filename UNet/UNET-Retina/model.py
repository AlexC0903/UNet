# -*- coding: utf-8 -*-
"""UNet

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1LJCVyG7nmdksuUiOWQ3puwm_3hB-QL2v
"""

import torch
import torch.nn as nn
import torchvision.transforms.functional as TF

# VGG block of 2 convolutions
class VGG2(nn.Module):
    def __init__(self, in_channels, out_channels):
        super(VGG2, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, 3, 1, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, 3, 1, 1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        x = self.conv(x)

        return x


# UNet
class UNet(nn.Module):
    def __init__(self, in_channels=3, out_channels=1):
        super(UNet, self).__init__()
        self.contractingPath = nn.ModuleList()
        self.expandingPath = nn.ModuleList()
        self.featureMapsC = [64, 128, 256, 512]
        self.featureMapsE = self.featureMapsC[::-1]
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

        # Contracting Path
        for i in range(len(self.featureMapsC)):
            self.contractingPath.append(VGG2(in_channels, self.featureMapsC[i]))
            in_channels = self.featureMapsC[i]

        in_channels = self.featureMapsE[0]
        # Expanding Path
        for i in range(len(self.featureMapsE)):
            self.expandingPath.append(
                nn.ConvTranspose2d(
                    self.featureMapsE[i] * 2,
                    self.featureMapsE[i],
                    kernel_size=2,
                    stride=2,
                )
            )
            self.expandingPath.append(
                VGG2(self.featureMapsE[i] * 2, self.featureMapsE[i])
            )

        # The "bottom" of the U Net
        self.bottomC = VGG2(self.featureMapsC[-1], self.featureMapsC[-1] * 2)

        # The final convolution of 1x1 kernel (reduces features)
        self.finalC = nn.Conv2d(self.featureMapsC[0], out_channels, 1)

    def forward(self, x):
        skip_connections = []
        # Run convolutions in self.contractingPath (pool after every Double Convolution)
        for i in range(len(self.contractingPath)):
            x = self.contractingPath[i](x)
            skip_connections.append(x)
            x = self.pool(x)

        # Run bottom Layer
        x = self.bottomC(x)
        # Flip the order of skip connections
        skip_connections = skip_connections[::-1]

        # Run convolutions in self.expandingPath
        for i in range(0, len(self.expandingPath), 2):
            x = self.expandingPath[i](x)  # Upsample
            skip_connection = skip_connections[i // 2]

            if x.shape != skip_connection.shape:
                x = TF.resize(x, size=skip_connection.shape[2:])

            concat_skip = torch.cat((skip_connection, x), dim=1)
            x = self.expandingPath[i + 1](concat_skip)

        x = self.finalC(x)
        return x


# UNet++
class UNetPP(nn.Module):
    def __init__(self, in_channels=3, out_channels=1, deep_supervision=False):
        super().__init__()
        features = [32, 64, 128, 256, 512]

        self.deep_supervision = deep_supervision
        self.pool = nn.MaxPool2d(2, 2)
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=True)

        self.conv0_0 = VGG2(in_channels, features[0])
        self.conv1_0 = VGG2(features[0], features[1])
        self.conv2_0 = VGG2(features[1], features[2])
        self.conv3_0 = VGG2(features[2], features[3])
        self.conv4_0 = VGG2(features[3], features[4])

        self.conv0_1 = VGG2(features[0] + features[1], features[0])
        self.conv1_1 = VGG2(features[1] + features[2], features[1])
        self.conv2_1 = VGG2(features[2] + features[3], features[2])
        self.conv3_1 = VGG2(features[3] + features[4], features[3])

        self.conv0_2 = VGG2(features[0] * 2 + features[1], features[0])
        self.conv1_2 = VGG2(features[1] * 2 + features[2], features[1])
        self.conv2_2 = VGG2(features[2] * 2 + features[3], features[2])

        self.conv0_3 = VGG2(features[0] * 3 + features[1], features[0])
        self.conv1_3 = VGG2(features[1] * 3 + features[2], features[1])

        self.conv0_4 = VGG2(features[0] * 4 + features[1], features[0])

        if deep_supervision:
            self.final1 = nn.Conv2d(features[0], out_channels, kernel_size=1)
            self.final2 = nn.Conv2d(features[0], out_channels, kernel_size=1)
            self.final3 = nn.Conv2d(features[0], out_channels, kernel_size=1)
            self.final4 = nn.Conv2d(features[0], out_channels, kernel_size=1)
        else:
            self.final = nn.Conv2d(features[0], out_channels, kernel_size=1)

    def forward(self, input):
        
        x0_0 = self.conv0_0(input)
        x1_0 = self.conv1_0(self.pool(x0_0))
        x0_1 = self.conv0_1(torch.cat([x0_0, self.up(x1_0)], 1))

        x2_0 = self.conv2_0(self.pool(x1_0))
        x1_1 = self.conv1_1(torch.cat([x1_0, self.up(x2_0)], 1))
        x0_2 = self.conv0_2(torch.cat([x0_0, x0_1, self.up(x1_1)], 1))

        x3_0 = self.conv3_0(self.pool(x2_0))
        x2_1 = self.conv2_1(torch.cat([x2_0, self.up(x3_0)], 1))
        x1_2 = self.conv1_2(torch.cat([x1_0, x1_1, self.up(x2_1)], 1))
        x0_3 = self.conv0_3(torch.cat([x0_0, x0_1, x0_2, self.up(x1_2)], 1))

        x4_0 = self.conv4_0(self.pool(x3_0))
        x3_1 = self.conv3_1(torch.cat([x3_0, self.up(x4_0)], 1))
        x2_2 = self.conv2_2(torch.cat([x2_0, x2_1, self.up(x3_1)], 1))
        x1_3 = self.conv1_3(torch.cat([x1_0, x1_1, x1_2, self.up(x2_2)], 1))
        x0_4 = self.conv0_4(torch.cat([x0_0, x0_1, x0_2, x0_3, self.up(x1_3)], 1))

        if self.deep_supervision:
            out1 = self.final1(x0_1)
            out2 = self.final2(x0_2)
            out3 = self.final3(x0_3)
            out4 = self.final4(x0_4)
            return [out1, out2, out3, out4]
        else:
            out = self.final(x0_4)
            return out

# Attention Gate(AG) for Attention U-Net
class AG(nn.Module):
    def __init__(self, f_g, f_l, f_int) -> None:
        super().__init__()   
        self.relu = nn.ReLU(inplace=True)
        
        self.w_g = nn.Sequential(
            nn.Conv2d(f_g, f_int, kernel_size=1, stride=1),
            nn.BatchNorm2d(f_int)
        )
        
        self.w_x = nn.Sequential(
            nn.Conv2d(f_l, f_int, kernel_size=1, stride=1),
            nn.BatchNorm2d(f_int)
        )
        
        self.psi = nn.Sequential(
            nn.Conv2d(f_int, 1, kernel_size=1, stride=1),
            nn.BatchNorm2d(1),
            nn.Sigmoid()
        )
        
    def forward(self, x_in, g_in):
        x = self.w_g(x_in)
        g = self.w_x(g_in)
        
        psi = self.relu(x+g)
        psi = self.psi(psi)
        
        out = x_in * psi

        return out

# Attention U-Net
class AUNet(nn.Module):
    def __init__(self, in_channels=3, out_channels=1) -> None:
        super().__init__()
        filters = [64, 128, 256, 512, 1024]
        self.relu = nn.ReLU(inplace=True)
        self.pool = nn.MaxPool2d(2, 2)
        self.up = nn.Upsample(
            scale_factor=2, mode="bilinear", align_corners=True)
        
        self.convC_1 = VGG2(in_channels, filters[0])
        self.convC_2 = VGG2(filters[0], filters[1])
        self.convC_3 = VGG2(filters[1], filters[2])
        self.convC_4 = VGG2(filters[2], filters[3])
        self.convC_5 = VGG2(filters[3], filters[4])
        
        self.convE_1 = VGG2(filters[4], filters[3])
        self.ag1 = AG(filters[3], filters[3], filters[2])
        
        self.convE_2 = VGG2(filters[3], filters[2])
        self.ag2 = AG(filters[2], filters[2], filters[1])
        
        self.convE_3 = VGG2(filters[2], filters[1])
        self.ag3 = AG(filters[1], filters[1], filters[0])
        
        self.convE_4 = VGG2(filters[1], filters[0])
        self.ag4 = AG(filters[0], filters[0], 32)
        
        self.finalConv = nn.Conv2d(32, out_channels, 1, 1)


    def forward(self, x):
        c_1 = self.convC_1(x)
        c_2 = self.convC_2(self.pool(c_1))
        c_3 = self.convC_3(self.pool(c_2))
        c_4 = self.convC_4(self.pool(c_3))
        c_5 = self.convC_5(self.pool(c_4))
        
        e_1 = self.convE_1(self.up(c_5))
        a_1 = self.ag1(e_1, c_4)
        e_2 = nn.Conv2d(1024, 512, 1, 1)(torch.cat([e_1, a_1], dim=1))
        
        
        e_3 = self.convE_2(self.up(e_2))
        a_2 = self.ag2(e_3, c_3)
        e_4 = nn.Conv2d(512, 256, 1, 1)(torch.cat([e_3, a_2], dim=1))
        
        e_5 = self.convE_3(self.up(e_4))
        a_3 = self.ag3(e_5, c_2)
        e_6 = nn.Conv2d(256, 128, 1, 1)(torch.cat([e_5, a_3], dim=1))
        
        e_7 = self.convE_4(self.up(e_6))
        a_4 = self.ag4(e_7, c_1)
        e_8 = nn.Conv2d(128, 32, 1, 1)(torch.cat([e_7, a_4], dim=1))
 
        out = self.finalConv(e_8)
        return out
        
        

def test():
    x = torch.randn((3, 1, 160, 160))
    model = AUNet(in_channels=1, out_channels=1)
    preds = model(x)
    assert preds.shape == x.shape
    print(preds.shape, x.shape)


if __name__ == "__main__":
    test()
