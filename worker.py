import numpy as np
import gym
import ray
import os
import logging
from preprocessor import Preprocessor
from utils.monitor import Monitor
from mixed_pg_learner import judge_is_nan

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# logger.setLevel(logging.INFO)


class OnPolicyWorker(object):
    """
    Act as both actor and learner
    """
    import tensorflow as tf
    # tf.config.experimental.set_visible_devices([], 'GPU')

    # gpus = tf.config.experimental.list_physical_devices('GPU')
    # tf.config.experimental.set_virtual_device_configuration(
    #     gpus[0],
    #     [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=1024)])

    def __init__(self, policy_cls, learner_cls, env_id, args, worker_id):
        logging.getLogger("tensorflow").setLevel(logging.ERROR)
        self.worker_id = worker_id
        self.args = args
        env = gym.make(env_id)
        self.env = Monitor(env)
        obs_space, act_space = self.env.observation_space, self.env.action_space
        self.learner = learner_cls(policy_cls, self.args)
        self.policy_with_value = policy_cls(obs_space, act_space, self.args)
        self.sample_batch_size = self.args.sample_batch_size
        self.obs = self.env.reset()
        # judge_is_nan([self.obs])
        self.done = False
        self.preprocessor = Preprocessor(obs_space, self.args.obs_preprocess_type, self.args.reward_preprocess_type,
                                         self.args.obs_scale_factor, self.args.reward_scale_factor,
                                         gamma=self.args.gamma)
        self.log_dir = self.args.log_dir

        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        if self.worker_id == 0:
            self.writer = self.tf.summary.create_file_writer(self.log_dir + '/worker')
            self.put_data_into_learner(*(self.sample()))
            self.learner.export_graph(self.writer)

        self.stats = {}
        logger.info('Worker initialized')

    def get_stats(self):
        return self.stats

    def save_weights(self, save_dir, iteration):
        self.policy_with_value.save_weights(save_dir, iteration)

    def load_weights(self, load_dir, iteration):
        self.policy_with_value.load_weights(load_dir, iteration)

    def get_weights(self):
        return self.policy_with_value.get_weights()

    def set_weights(self, weights):
        return self.policy_with_value.set_weights(weights)

    def apply_gradients(self, iteration, grads):
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
        epinfos = []
        for _ in range(self.sample_batch_size):
            processed_obs = self.preprocessor.process_obs(self.obs)
            # judge_is_nan([processed_obs])

            action, neglogp = self.policy_with_value.compute_action(processed_obs[np.newaxis, :])  # TODO
            # judge_is_nan([action])
            # judge_is_nan([neglogp])
            # print(action[0].numpy())
            obs_tp1, reward, self.done, info = self.env.step(action[0].numpy())
            processed_rew = self.preprocessor.process_rew(reward, self.done)
            # judge_is_nan([obs_tp1])

            batch_data.append((self.obs, action[0].numpy(), reward, obs_tp1, self.done, neglogp[0].numpy()))
            self.obs = self.env.reset() if self.done else obs_tp1.copy()
            maybeepinfo = info.get('episode')
            if maybeepinfo: epinfos.append(maybeepinfo)
            # judge_is_nan([self.obs])

        return batch_data, epinfos

    def put_data_into_learner(self, batch_data, epinfos):
        self.learner.set_ppc_params(self.get_ppc_params())
        self.learner.get_batch_data(batch_data, epinfos)

    def compute_gradient_over_ith_minibatch(self, i):
        self.learner.set_weights(self.get_weights())
        grad = self.learner.compute_gradient_over_ith_minibatch(i)
        learner_stats = self.learner.get_stats()
        self.stats.update(dict(learner_stats=learner_stats))
        return grad


if __name__ == '__main__':
    pass
