# %%
import os
import time
import spwk_agtech
import gym
import numpy as np
import argparse

from datetime import datetime
from td3_torch import Agent
from torch.utils.tensorboard import SummaryWriter

# %%
assert os.environ['CONDA_DEFAULT_ENV'] == 'spacewalk', 'Switch to correct environment!'

# %%
def parse_arguments(parser):
    parser.add_argument('--alpha',          type=float, default=0.001,  help='Learning Rate for the Actor (float)')
    parser.add_argument('--beta',           type=float, default=0.001,  help='Learning Rate for the Critic (float')
    parser.add_argument('--tau',            type=float, default=0.005,  help='Controls soft updating the target network')
    parser.add_argument('--update_act_int', type=int,   default=2,      help='Update actor interval')
    parser.add_argument('--batch_size',     type=int,   default=100,    help='Batch Size for Actor & Critic training')
    parser.add_argument('--layer1_size',    type=int,   default=400,    help='Layer 1 size (same for actor & critic)')
    parser.add_argument('--layer2_size',    type=int,   default=300,    help='Layer 2 size (same for actor & critic)')
    parser.add_argument('--n_games',        type=int,   default=10000,  help='Total number of episodes')
    parser.add_argument('--patience',       type=int,   default=1000,   help='Patience for plateau checking')
    parser.add_argument('--TB_note',        type=str,   default="",     help='Note on TensorBoard')

    args = parser.parse_args()

    return args

# %%
def get_writer_name(args):
    writer_name = \
        "TD3_PCSE_alpha_{}_beta_{}_tau_{}_UpdActInt_{}_batchsize_{}_layer1size_{}_layer2size_{}_nGames_{}_patience_{}_{}".format(
            args.alpha, args.beta, args.tau, args.update_act_int, args.batch_size, args.layer1_size, args.layer2_size, 
            args.n_games, args.patience, datetime.now().strftime("%Y%m%d_%H%M")
        )

    if args.TB_note != "":
        writer_name += "_" + args.TB_note

    writer_name = './TB/' + writer_name
    print('TensorBoard Name: {}'.format(writer_name))

    return writer_name

# %%
def has_plateaued(reward_history, patience=100):
    ''' Simple function that checks for plateau. '''
    single_patience_mean = np.mean(reward_history[-patience:])
    double_patience_mean = np.mean(reward_history[-2*patience:])

    if len(reward_history) < 2*patience:
        return False

    plateau_bool = np.abs((single_patience_mean - double_patience_mean) / single_patience_mean)*100 < 0.1

    return plateau_bool

# %%
def train_TD3(args, writer):
    train_begin_time = time.time()

    env = gym.make('PCSE-v0')
    agent = Agent(alpha=args.alpha, beta=args.beta, input_dims=env.observation_space.shape,
                    tau=args.tau, env=env, update_actor_interval=args.update_act_int,
                    batch_size=args.batch_size, layer1_size=args.layer1_size, 
                    layer2_size=args.layer2_size, n_actions=env.action_space.shape[0])

    best_score = env.reward_range[0]
    reward_history = []
    mean_reward_history = []
    
    for i in range(args.n_games):
        obs = env.reset()
        done = False
        reward_sum = 0
        while not done:
            action = agent.choose_action(obs)
            obs_, reward, done, _ = env.step(action)
            agent.remember(obs, action, reward, obs_, done)
            agent.learn()
            reward_sum += reward
            obs = obs_

        reward_history.append(reward_sum)
        writer.add_scalar('Reward', reward_sum, i)
        avg_score = np.mean(reward_history[-100:])
        mean_reward_history.append(avg_score)
        writer.add_scalar('last_100_score_avg', avg_score, i)

        if avg_score > best_score:
            best_score = avg_score
            agent.save_models()
        
        writer.add_scalar('best_score_so_far', best_score, i)

        if i % 1 == 0:
            print('Episode: {:<6s}\tScore: {:<10s}\tLast 100 Episode Avg.: {:<15s}\tTrain Time: {:.1f} sec'.format(
                str(i), str(np.round(reward_sum, 2)), str(np.round(avg_score, 2)), time.time()-train_begin_time))

        if has_plateaued(mean_reward_history, patience=args.patience):
            print("\nReached Plateau; Terminating Simulations.\n")
            print("Writer: {}".format(writer.log_dir))
            break

# %%
if __name__=='__main__':
    parser = argparse.ArgumentParser(description='Hyperparameters for TD3') # Parse hyperparameter arguments from CLI
    args = parse_arguments(parser) # Reference values like so: args.alpha 

    writer_name = get_writer_name(args)
    writer = SummaryWriter(writer_name)

    train_TD3(args, writer)
