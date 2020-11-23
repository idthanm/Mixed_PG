#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =====================================
# @Time    : 2020/8/10
# @Author  : Yang Guan (Tsinghua Univ.)
# @FileName: model.py
# =====================================

import tensorflow as tf
from tensorflow import Variable
from tensorflow.keras import Model, Sequential
from tensorflow.keras.layers import Dense
import numpy as np

tf.config.experimental.set_visible_devices([], 'GPU')

def ortho_init(scale=1.0):
    def _ortho_init(shape, dtype, partition_info=None):
        #lasagne ortho init for tf
        shape = tuple(shape)
        if len(shape) == 2:
            flat_shape = shape
        elif len(shape) == 4: # assumes NHWC
            flat_shape = (np.prod(shape[:-1]), shape[-1])
        else:
            raise NotImplementedError
        a = np.random.normal(0.0, 1.0, flat_shape)
        u, _, v = np.linalg.svd(a, full_matrices=False)
        q = u if u.shape == flat_shape else v # pick the one with the correct shape
        q = q.reshape(shape)
        return (scale * q[:shape[0], :shape[1]]).astype(np.float32)
    return _ortho_init


class MLPNet(Model):
    def __init__(self, input_dim, num_hidden_layers, num_hidden_units, hidden_activation, output_dim, **kwargs):
        super(MLPNet, self).__init__(name=kwargs['name'])
        self.first_ = Dense(num_hidden_units,
                            activation=hidden_activation,
                            kernel_initializer=ortho_init(np.sqrt(2.)),  # tf.keras.initializers.Orthogonal(1.414),
                            # bias_initializer=tf.keras.initializers.Constant(0.),
                            dtype=tf.float32)
        self.hidden = Sequential([Dense(num_hidden_units,
                                        activation=hidden_activation,
                                        kernel_initializer=ortho_init(np.sqrt(2.)),  # tf.keras.initializers.Orthogonal(1.414),
                                        # bias_initializer=tf.keras.initializers.Constant(0.),
                                        dtype=tf.float32) for _ in range(num_hidden_layers-1)])
        output_activation = kwargs['output_activation'] if kwargs.get('output_activation') else 'linear'
        self.outputs = Dense(output_dim,
                             activation=output_activation,
                             kernel_initializer=ortho_init(1.),  # tf.keras.initializers.Orthogonal(1.414),
                             bias_initializer=tf.keras.initializers.Constant(0.),
                             dtype=tf.float32)
        self.build(input_shape=(None, input_dim))

    def call(self, x, **kwargs):
        x = self.first_(x)
        x = self.hidden(x)
        x = self.outputs(x)
        return x


class PPONet(Model):
    def __init__(self, input_dim, num_hidden_layers, num_hidden_units, hidden_activation, output_dim, **kwargs):
        super(PPONet, self).__init__(name=kwargs['name'])
        self.first_ = Dense(num_hidden_units,
                            activation=hidden_activation,
                            kernel_initializer=ortho_init(np.sqrt(2.)),  # tf.keras.initializers.Orthogonal(1.414),
                            dtype=tf.float32)
        self.sec_ = Dense(num_hidden_units,
                          activation=hidden_activation,
                          kernel_initializer=ortho_init(np.sqrt(2.)),  # tf.keras.initializers.Orthogonal(1.414),
                          dtype=tf.float32)
        output_activation = kwargs['output_activation'] if kwargs.get('output_activation') else 'linear'
        self.mean = Dense(int(output_dim/2),
                          activation=output_activation,
                          kernel_initializer=ortho_init(0.01),  # tf.keras.initializers.Orthogonal(1.414),
                          bias_initializer=tf.keras.initializers.Constant(0.),
                          dtype=tf.float32)
        self.logstd = tf.Variable(initial_value=tf.zeros((1, int(output_dim/2))), name='pi/logstd', dtype=tf.float32)
        self.build(input_shape=(None, input_dim))

    def call(self, x, **kwargs):
        x = self.first_(x)
        x = self.sec_(x)
        mean = self.mean(x)
        out = tf.concat([mean, mean * tf.constant(0.) + self.logstd], axis=1)
        return out



def test_attrib():
    a = Variable(0, name='d')

    p = MLPNet(2, 2, 128, 1, name='ttt')
    print(hasattr(p, 'get_weights'))
    print(hasattr(p, 'trainable_weights'))
    print(hasattr(a, 'get_weights'))
    print(hasattr(a, 'trainable_weights'))
    print(type(a))
    print(type(p))
    # print(a.name)
    # print(p.name)
    # p.build((None, 2))
    p.summary()
    # inp = np.random.random([10, 2])
    # out = p.forward(inp)
    # print(p.get_weights())
    # print(p.trainable_weights)


def test_clone():
    p = MLPNet(2, 2, 128, 1, name='ttt')
    print(p._is_graph_network)
    s = tf.keras.models.clone_model(p)
    print(s)


def test_out():
    import numpy as np
    Qs = tuple(MLPNet(8, 2, 128, 1, name='Q' + str(i)) for i in range(2))
    inp = np.random.random((128, 8))
    out = [Q(inp) for Q in Qs]
    print(out)

def test_dense():
    first_ = Dense(3,
                kernel_initializer=tf.keras.initializers.Orthogonal(1.414),
                dtype=tf.float32)
    first_.build(input_shape=(3.))
    print(1)


def test_dsac_net():
    import numpy as np
    net = MLPNetDSAC(3, 0, 256, 4, name='policy')
    inpu = np.array([[1.,2., 3.]])
    out = net(inpu)
    print(out)

def test_ppo_net():
    import numpy as np
    net = PPONet(3, 2, 64, 'tanh', 2, name='policy')

    def out(net, inpu):
        out = net(inpu)
        return out

    inpu = np.random.random((10, 3))
    print(out(net, inpu))

def test_sequ():
    def create_a_sequ_model():
        model = tf.keras.Sequential([Dense(30, activation='tanh'),
                                     Dense(20, activation='tanh')])
        model.build(input_shape=(None, 3))
        print(model.summary())
        return model
    model = create_a_sequ_model()

    inpu = np.random.random((10, 3))
    out = model(inpu)
    print(out)

def test_funcapi():
    def create_funcapi_model():
        inpu = tf.keras.Input(shape=(3,))
        x = Dense(20, activation='tanh')(inpu)
        out = Dense(20, activation='tanh')(x)
        model = tf.keras.Model(inputs=inpu, outputs=out)
        print(model.summary())
        return model
    model = create_funcapi_model()
    inpu = np.random.random((10, 3))
    out = model(inpu)
    print(out)


if __name__ == '__main__':
    test_sequ()
