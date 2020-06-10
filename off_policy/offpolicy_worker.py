#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =====================================
# @Time    : 2020/6/10
# @Author  : Yang Guan (Tsinghua Univ.)
# @FileName: offpolicy_worker.py
# =====================================

import logging

import gym
import numpy as np

from preprocessor import Preprocessor

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# logger.setLevel(logging.INFO)


class OffPolicyWorker(object):
    """just for sample"""

    def __init__(self, policy_cls, env_id, args, worker_id):
        logging.getLogger("tensorflow").setLevel(logging.ERROR)
        self.worker_id = worker_id
        self.args = args
        self.env = gym.make(env_id,
                            training_task=self.args.training_task,
                            num_future_data=self.args.num_future_data)
        obs_space, act_space = self.env.observation_space, self.env.action_space
        self.policy_with_value = policy_cls(obs_space, act_space, self.args)
        self.batch_size = self.args.batch_size
        self.obs = self.env.reset()
        self.done = False
        self.preprocessor = Preprocessor(obs_space, self.args.obs_preprocess_type, self.args.reward_preprocess_type,
                                         self.args.obs_scale_factor, self.args.reward_scale_factor,
                                         gamma=self.args.gamma)

        self.iteration = 0
        logger.info('Worker initialized')

    def save_weights(self, save_dir, iteration):
        self.policy_with_value.save_weights(save_dir, iteration)

    def load_weights(self, load_dir, iteration):
        self.policy_with_value.load_weights(load_dir, iteration)

    def get_weights(self):
        return self.policy_with_value.get_weights()

    def set_weights(self, weights):
        return self.policy_with_value.set_weights(weights)

    def apply_gradients(self, iteration, grads):
        self.iteration = iteration
        self.policy_with_value.apply_gradients(iteration, grads)

    def get_ppc_params(self):
        return self.preprocessor.get_params()

    def set_ppc_params(self, params):
        self.preprocessor.set_params(params)

    def save_ppc_params(self, save_dir):
        self.preprocessor.save_params(save_dir)

    def load_ppc_params(self, load_dir):
        self.preprocessor.load_params(load_dir)

    def sample(self):
        batch_data = []
        for _ in range(self.batch_size):
            processed_obs = self.preprocessor.process_obs(self.obs)
            action, neglogp = self.policy_with_value.compute_action(processed_obs[np.newaxis, :])
            obs_tp1, reward, self.done, info = self.env.step(action[0].numpy())
            processed_rew = self.preprocessor.process_rew(reward, self.done)
            batch_data.append((self.obs, action[0].numpy(), reward, obs_tp1, self.done))
            self.obs = self.env.reset() if self.done else obs_tp1
            # self.env.render()

        return batch_data

    def sample_with_count(self):
        batch_data = self.sample()
        return batch_data, len(batch_data)