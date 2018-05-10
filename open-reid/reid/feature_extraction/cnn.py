from __future__ import absolute_import
from collections import OrderedDict

from torch.autograd import Variable

import sys
sys.path.append('/export/livia/home/vision/FHafner/masterthesis/open-reid/reid/')

from utils import to_torch


def extract_cnn_feature(model, inputs, modules=None):
    # evaluation mode
    model.eval()
    inputs = to_torch(inputs)
    inputs = Variable(inputs, volatile=True)
    #Q: What are modules?
    if modules is None:
        outputs = model(inputs)
        outputs = outputs.data.cpu()
        return outputs
    # Register forward hook for each module
    outputs = OrderedDict()
    handles = []
    for m in modules:
        outputs[id(m)] = None
        def func(m, i, o): outputs[id(m)] = o.data.cpu()
        handles.append(m.register_forward_hook(func))
    model(inputs)
    for h in handles:
        h.remove()
    return list(outputs.values())
