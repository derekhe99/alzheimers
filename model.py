import torch
import torch.nn as nn
import os
import argparse
import numpy as np
import PIL as Image
from scipy.misc import imresize
import torch.utils.data as data
import torchvision
from torchvision import datasets, transforms
from torch.autograd import Variable
import time
import torch.optim as optim
from torch.optim import lr_scheduler
import confusionmeter
import sys
import shutil
from resnet.pretrainedmodels.inceptionresnetv2 import *


model = inceptionresnetv2(num_classes=1000,pretrained='imagenet')
num_ftrs = model.classif.in_features
model.classif = nn.Linear(num_ftrs, 5)


######################################
## Custom data transforms
#####################################


data_transforms = {
    'train': transforms.Compose([
            transforms.Scale(299),
            transforms.ToTensor(),
            transforms.Normalize([0.122,0.122,0.122], [0.250,0.250,0.250])
    ]),
    'test': transforms.Compose([
            transforms.Scale(299),
            transforms.ToTensor(),
            transforms.Normalize([0.122,0.122,0.122], [0.250,0.250,0.250])
    ])
}


#####################################
## Load Data
#####################################

data_dir = '../imgdata'
image_datasets = {x: datasets.ImageFolder(os.path.join(data_dir, x),
                    data_transforms[x]) for x in ['train', 'test']}
dataloaders = {x: torch.utils.data.DataLoader(image_datasets[x], batch_size=128,
                    shuffle=True, num_workers=16) for x in ['train', 'test']}
dataset_sizes= {x: len(image_datasets[x]) for x in ['train', 'test']}
classnames = image_datasets['train'].classes

use_gpu = torch.cuda.is_available()

####################################
## End Data Loading
####################################


####################################
## Train Model
####################################

def train_model(model, criterion, optimizer, scheduler, num_epochs=25):
    since = time.time()

    if use_gpu:
        model = nn.DataParallel(model, device_ids=[0,1,2,3]).cuda()

    best_model_wts = model.state_dict()
    best_acc = 0.0

    for epoch in range(num_epochs):
        print('Epoch {}/{}'.format(epoch, num_epochs - 1))
        print('-' * 10)
        # Each epoch has a training and validation phase
        for phase in ['train', 'test']:
            if phase == 'train':
                scheduler.step()
                model.train(True)  # Set model to training mode
            else:
                model.train(False)  # Set model to evaluate mode

            running_loss = 0.0
            running_corrects = 0
            i=0
            # Iterate over data.
            for data in dataloaders[phase]:
                i+=1
                # get the inputs
                inputs, labels = data

                # wrap them in Variable
                if use_gpu:
                    inputs = Variable(inputs.cuda())
                    labels = Variable(labels.cuda())
                else:
                    inputs, labels = Variable(inputs), Variable(labels)

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward
                outputs = model(inputs)


                _, preds = torch.max(outputs.data, 1)
                loss = criterion(outputs, labels)


                # backward + optimize only if in training phase
                if phase == 'train':
                    loss.backward()
                    optimizer.step()

                # statistics
                running_loss += loss.data[0]
                running_corrects += torch.sum(preds == labels.data)

                if i%10==0:
                    print(epoch, running_corrects/(i*128.0))

            epoch_loss = running_loss / dataset_sizes[phase]
            epoch_acc = running_corrects / dataset_sizes[phase]

            print('{} Loss: {:.4f} Acc: {:.4f}'.format(
                phase, epoch_loss, epoch_acc))

            # deep copy the model
            if phase == 'test' and epoch_acc > best_acc:
                best_acc = epoch_acc
                model.save_state_dict("mymodel.pt")
        print()

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
    print('Best val Acc: {:4f}'.format(best_acc))

    # load best model weights
    model.load_state_dict(best_model_wts)
    return model


opt = optim.SGD(model.parameters(), lr=0.001, momentum=0.5)
criterion = nn.CrossEntropyLoss()
exp_lr_scheduler = lr_scheduler.StepLR(opt, step_size=7, gamma=0.1)
model = train_model(model, criterion, opt, exp_lr_scheduler, num_epochs=5)
model.save_state_dict('finalmodel.pt')

#end
