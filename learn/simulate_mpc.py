import os
import sys
from dotmap import DotMap

# add cwd to path to allow running directly from the repo top level directory
sys.path.append(os.getcwd())

import pandas as pd
import numpy as np
import torch
import math

from learn.control.random import RandomController
from learn.control.mpc import MPController
from learn import envs
from learn.trainer import train_model
import gym
import logging
import hydra
from learn.utils.plotly import plot_rewards_over_trials, plot_rollout

log = logging.getLogger(__name__)


def save_log(cfg, trial_num, trial_log):
    name = cfg.checkpoint_file.format(trial_num)
    path = os.path.join(os.getcwd(), name)
    log.info(f"T{trial_num} : Saving log {path}")
    torch.save(trial_log, path)


######################################################################
@hydra.main(config_path='conf/learn.yaml')
def mpc(cfg):
    log.info("============= Configuration =============")
    log.info(f"Config:\n{cfg.pretty()}")
    log.info("=========================================")

    env_name = 'CrazyflieRigid-v0'
    env = gym.make(env_name)
    env.reset()
    full_rewards = []

    for s in range(cfg.experiment.seeds):
        trial_rewards = []
        log.info(f"Random Seed: {s}")
        data = rollout(env, RandomController(env, cfg.policy), cfg.experiment)
        X, dX, U = to_XUdX(data)

        model, train_log = train_model(X, U, dX, cfg.model)

        for i in range(cfg.experiment.num_r):
            controller = MPController(env, model, cfg.policy)

            raise NotImplementedError("")
            while r < cfg.experiment.repeat:
                states, actions, rews, sim_error = rollout(env, controller, cfg.experiment)
                if sim_error:
                    print("Repeating strange simulation")
                    continue
                cum_cost.append(-1 * np.sum(rews) / len(rews))  # for minimization
                r += 1


            data_new = rollout(env, controller, cfg.experiment)
            rew = np.stack(data_new[2])

            X, dX, U = combine_data(data_new, (X, dX, U))
            msg = "Rollout completed of "
            msg += f"Cumulative reward {np.sum(np.stack(data_new[2]))}, "
            msg += f"Flight length {len(np.stack(data_new[2]))}"
            log.info(msg)

            plot_rollout(data_new[0], data_new[1])

            reward = np.sum(rew)
            # reward = max(-10000, reward)
            trial_rewards.append(reward)

            trial_log = dict(
                env_name=cfg.env.params.name,
                seed=cfg.random_seed,
                trial_num=i,
                rewards=trial_rewards,
                nll=train_log,
            )
            save_log(cfg, i, trial_log)

            model, train_log = train_model(X, U, dX, cfg.model)
        full_rewards.append(trial_rewards)

    plot_rewards_over_trials(full_rewards, env_name)


def to_XUdX(data):
    states = np.stack(data[0])
    X = states[:-1, :]
    dX = states[1:, :] - states[:-1, :]
    U = np.stack(data[1])[:-1, :]
    return X, dX, U


def combine_data(new_data, full_data):
    X_new, dX_new, U_new = to_XUdX(new_data)
    X = np.concatenate((full_data[0], X_new), axis=0)
    U = np.concatenate((full_data[2], U_new), axis=0)
    dX = np.concatenate((full_data[1], dX_new), axis=0)
    return X, dX, U


def rollout(env, controller, exp_cfg):
    done = False
    states = []
    actions = []
    rews = []
    state = env.reset()
    for t in range(exp_cfg.r_len):
        last_state = state
        if done:
            break
        action, update = controller.get_action(state)
        # if update:
        states.append(state)
        actions.append(action)

        state, rew, done, _ = env.step(action)
        sim_error = euler_numer(last_state, state)
        done = done or sim_error
        # if update:
        rews.append(rew)

    return states, actions, rews


def euler_numer(last_state, state):
    flag = False
    if abs(state[3] - last_state[3]) > 5:
        flag = True
    elif abs(state[4] - last_state[4]) > 5:
        flag = True
    elif abs(state[5] - last_state[5]) > 5:
        flag = True
    if flag:
        print("Stopping - Large euler angle step detected, likely non-physical")
    return flag


if __name__ == '__main__':
    sys.exit(mpc())
