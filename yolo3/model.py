#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
create YOLOv3 models with different backbone & head
"""
import tensorflow.keras.backend as K
from tensorflow.keras.layers import Input, Lambda
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from yolo3.models.yolo3_darknet import yolo_body, tiny_yolo_body, custom_tiny_yolo_body, tiny_yololite_body
from yolo3.models.yolo3_mobilenet import yolo_mobilenet_body, tiny_yolo_mobilenet_body, yololite_mobilenet_body, tiny_yololite_mobilenet_body
from yolo3.models.yolo3_vgg16 import yolo_vgg16_body, tiny_yolo_vgg16_body
from yolo3.models.yolo3_xception import yolo_xception_body, yololite_xception_body, tiny_yolo_xception_body, tiny_yololite_xception_body
from yolo3.loss import yolo_loss
from yolo3.utils import add_metrics


def get_model_body(model_type, is_tiny_version, image_input, num_anchors, num_classes):
    if is_tiny_version:
        if model_type == 'mobilenet_lite':
            model_body = tiny_yololite_mobilenet_body(image_input, num_anchors//2, num_classes)
            backbone_len = 87
        elif model_type == 'mobilenet':
            model_body = tiny_yolo_mobilenet_body(image_input, num_anchors//2, num_classes)
            backbone_len = 87
        elif model_type == 'darknet':
            weights_path='model_data/tiny_yolo_weights.h5'
            model_body = custom_tiny_yolo_body(image_input, num_anchors//2, num_classes, weights_path)
            backbone_len = 20
        elif model_type == 'darknet_lite':
            model_body = tiny_yololite_body(image_input, num_anchors//2, num_classes)
            #Doesn't have pretrained weights, so no need to return backbone length
            backbone_len = 0
        elif model_type == 'vgg16':
            model_body = tiny_yolo_vgg16_body(image_input, num_anchors//2, num_classes)
            backbone_len = 19
        elif model_type == 'xception':
            model_body = tiny_yolo_xception_body(image_input, num_anchors//2, num_classes)
            backbone_len = 132
        elif model_type == 'xception_lite':
            model_body = tiny_yololite_xception_body(image_input, num_anchors//2, num_classes)
            backbone_len = 132
        else:
            raise ValueError('Unsupported model type')
    else:
        if model_type == 'mobilenet_lite':
            model_body = yololite_mobilenet_body(image_input, num_anchors//3, num_classes)
            backbone_len = 87
        elif model_type == 'mobilenet':
            model_body = yolo_mobilenet_body(image_input, num_anchors//3, num_classes)
            backbone_len = 87
        elif model_type == 'darknet':
            weights_path='model_data/darknet53_weights.h5'
            model_body = yolo_body(image_input, num_anchors//3, num_classes, weights_path=weights_path)
            backbone_len = 185
        elif model_type == 'vgg16':
            model_body = yolo_vgg16_body(image_input, num_anchors//3, num_classes)
            backbone_len = 19
        elif model_type == 'xception':
            model_body = yolo_xception_body(image_input, num_anchors//3, num_classes)
            backbone_len = 132
        elif model_type == 'xception_lite':
            model_body = yololite_xception_body(image_input, num_anchors//3, num_classes)
            backbone_len = 132
        else:
            raise ValueError('Unsupported model type')
    return model_body, backbone_len


def get_yolo3_model(model_type, input_shape, anchors, num_classes, weights_path=None, freeze_level=1, learning_rate=1e-3):
    '''create the training model, for YOLOv3'''
    K.clear_session() # get a new session
    num_anchors = len(anchors)
    is_tiny_version = num_anchors==6 # default setting

    h, w = input_shape
    image_input = Input(shape=(None, None, 3))
    if is_tiny_version:
        y_true = [Input(shape=(h//{0:32, 1:16}[l], w//{0:32, 1:16}[l], \
            num_anchors//2, num_classes+5)) for l in range(2)]
    else:
        y_true = [Input(shape=(h//{0:32, 1:16, 2:8}[l], w//{0:32, 1:16, 2:8}[l], \
            num_anchors//3, num_classes+5)) for l in range(3)]

    model_body, backbone_len = get_model_body(model_type, is_tiny_version, image_input, num_anchors, num_classes)
    print('Create {} YOLOv3 {} model with {} anchors and {} classes.'.format('Tiny' if is_tiny_version else '', model_type, num_anchors, num_classes))

    if weights_path:
        model_body.load_weights(weights_path, by_name=True)#, skip_mismatch=True)
        print('Load weights {}.'.format(weights_path))

    if freeze_level in [1, 2]:
        # Freeze the backbone part or freeze all but final feature map & input layers.
        num = (backbone_len, len(model_body.layers)-3)[freeze_level-1]
        for i in range(num): model_body.layers[i].trainable = False
        print('Freeze the first {} layers of total {} layers.'.format(num, len(model_body.layers)))
    elif freeze_level == 0:
        # Unfreeze all layers.
        for i in range(len(model_body.layers)):
            model_body.layers[i].trainable= True
        print('Unfreeze all of the layers.')

    model_loss, xy_loss, wh_loss, confidence_loss, class_loss = Lambda(yolo_loss, output_shape=(1,), name='yolo_loss',
        arguments={'anchors': anchors, 'num_classes': num_classes, 'ignore_thresh': 0.5, 'use_focal_loss': False, 'use_softmax_loss': False})(
        [*model_body.output, *y_true])
    model = Model([model_body.input, *y_true], model_loss)

    model.compile(optimizer=Adam(lr=learning_rate), loss={
        # use custom yolo_loss Lambda layer.
        'yolo_loss': lambda y_true, y_pred: y_pred})

    loss_dict = {'xy_loss':xy_loss, 'wh_loss':wh_loss, 'confidence_loss':confidence_loss, 'class_loss':class_loss}
    add_metrics(model, loss_dict)

    return model
