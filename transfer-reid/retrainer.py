from __future__ import print_function, absolute_import

import torch
from torchvision import transforms
from torch.autograd import Variable

from torch.utils.data import DataLoader


from PIL import Image
import sys
import models
from torch import nn
import datasets
import models
from dist_metric import DistanceMetric
from loss import TripletLoss
from trainers import TrainerRetrainer
from evaluators import Evaluator
from utils.data import transforms as T
from utils.data.preprocessor import PreprocessorRetrain
from utils.data.preprocessor import Preprocessor

from utils.data.sampler import RandomIdentitySampler
from utils.logging import Logger
from utils.serialization import load_checkpoint, save_checkpoint
import pickle
sys.path.append('/export/livia/home/vision/FHafner/masterthesis/open-reid/reid')
sys.path.append('/export/livia/home/vision/FHafner/masterthesis/open-reid/reid/utils')


class Retrainer:
    def __init__(self, path_to_model, dropout=0):
        self.path_to_model = path_to_model
        self.dropout = dropout
        self.load_model()
        pass

    def load_model(self):
        name_dict = {
            110: 'resnet18',
            203: 'inception',
            275: 'resnet50',
        }

        checkpoint = torch.load(self.path_to_model)
        self.model_arch = name_dict[len(checkpoint['state_dict'])]
        self.num_features = checkpoint['state_dict']['classifier.weight'].shape[1]
        self.num_classes = checkpoint['state_dict']['classifier.weight'].shape[0]
        self.model = models.create(self.model_arch, num_features=self.num_features,
                          dropout=self.dropout, num_classes=self.num_classes)
        self.model.load_state_dict(checkpoint['state_dict'])
        self.model.cuda()

    def retrain(self, dataset, path_to_gt, root='/export/livia/home/vision/FHafner/masterthesis/open-reid/examples/data',
                epochs=50, split_id=0, start_epoch=0, batch_size=64, workers=2, combine_trainval=False):

        if self.model_arch == 'inception':
            height, width = (144, 56)
        else:
            height, width = (256, 128)

        dataset, num_classes, train_loader, val_loader, test_loader = get_data(dataset, split_id, root, height,
                                                                                   width, batch_size, workers,
                                                                                   combine_trainval, path_to_gt)

        self.model.cuda()

        criterion = nn.MSELoss().cuda()
        param_groups = self.model.parameters()

        optimizer = torch.optim.SGD(param_groups, lr=0.1,
                                         momentum=0.9,
                                         weight_decay=5e-4,
                                         nesterov=True)

        metric = DistanceMetric(algorithm='euclidean')

        trainer = TrainerRetrainer(self.model, criterion)

        for epoch in range(start_epoch, epochs):
            trainer.train(epoch, train_loader, optimizer)


def get_data(name, split_id, data_dir, height, width, batch_size, workers,
             combine_trainval, path_to_gt):
    root = data_dir + '/' + name

    dataset = datasets.create(name, root, split_id=split_id)

    normalizer = T.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])

    train_set = dataset.trainval if combine_trainval else dataset.train
    num_classes = (dataset.num_trainval_ids if combine_trainval
                   else dataset.num_train_ids)

    train_transformer = T.Compose([
        T.RandomSizedRectCrop(height, width),
        T.RandomHorizontalFlip(),
        T.ToTensor(),
        normalizer,
    ])

    test_transformer = T.Compose([
        T.RectScale(height, width),
        T.ToTensor(),
        normalizer,
    ])

    train_set = pickle.load(open(path_to_gt + 'gt.txt', "rb"))

    train_loader = DataLoader(
        PreprocessorRetrain(train_set, root=dataset.images_dir,
                     transform=train_transformer),
        batch_size=batch_size, num_workers=workers,
        shuffle=True, pin_memory=True, drop_last=False)

    val_loader = DataLoader(
        Preprocessor(dataset.val, root=dataset.images_dir,
                     transform=test_transformer),
        batch_size=batch_size, num_workers=workers,
        shuffle=False, pin_memory=False)

    test_loader = DataLoader(
        Preprocessor(list(set(dataset.query) | set(dataset.gallery)),
                     root=dataset.images_dir, transform=test_transformer),
        batch_size=batch_size, num_workers=workers,
        shuffle=False, pin_memory=False)

    return dataset, num_classes, train_loader, val_loader, test_loader
