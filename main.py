# main function that sets up environments
# perform training loop

from maddpg import MADDPG
from memory import ReplayBuffer
import torch
import numpy as np
import os
from unityagents import UnityEnvironment
from util import raw_score_plotter, plotter


from collections import deque


def seeding(seed=1):
    np.random.seed(seed)
    torch.manual_seed(seed)

def main():
    seeding()
    # number of parallel agents

    env = UnityEnvironment(file_name="Tennis.x86_64")
    env_name = 'Tennis'

    # get the default brain
    brain_name = env.brain_names[0]
    brain = env.brains[brain_name]
    env_info = env.reset(train_mode=True)[brain_name]
    # number of agents
    num_agents = len(env_info.agents)

    # size of each action
    action_size = brain.vector_action_space_size

    # examine the state space
    states = env_info.vector_observations
    state_size = states.shape[-1]

    # number of training episodes.
    # change this to higher number to experiment. say 30000.
    number_of_episodes = 10000
    episode_length = 10000
    batchsize = 128

    # amplitude of OU noise
    # this slowly decreases to 0
    noise = 1
    noise_reduction = 0.9999

    log_path = os.getcwd() + "/log"
    model_dir = os.getcwd() + "/model_dir"

    os.makedirs(model_dir, exist_ok=True)

    # initialize memory buffer
    buffer = ReplayBuffer(int(500000), batchsize, 0)

    # initialize policy and critic
    maddpg = MADDPG(state_size, action_size, num_agents, seed=12345, discount_factor=0.95, tau=0.02)

    #how often to update the MADDPG model
    episode_per_update = 2
    # training loop

    PRINT_EVERY = 5
    scores_deque = deque(maxlen=100)

    # holds raw scores
    scores = []
    # holds avg scores of last 100 epsiodes
    avg_last_100 = []

    threshold = 0.5

    # use keep_awake to keep workspace from disconnecting
    for episode in range(number_of_episodes):

        env_info = env.reset(train_mode=True)[brain_name]  # reset the environment
        state = env_info.vector_observations  # get the current state (for each agent)
        episode_reward_agent0 = 0
        episode_reward_agent1 = 0


        for agent in maddpg.maddpg_agent:
            agent.noise.reset()

        for episode_t in range(episode_length):

            actions = maddpg.act(torch.tensor(state, dtype=torch.float), noise=noise)
            noise *= noise_reduction

            actions_array = torch.stack(actions).detach().numpy()

            env_info = env.step(actions_array)[brain_name]
            next_state = env_info.vector_observations

            reward = env_info.rewards
            done = env_info.local_done

            episode_reward_agent0 += reward[0]
            episode_reward_agent1 += reward[1]
            # add data to buffer

            '''
            I can either hstack or concat two states here or do it in the update function in MADDPG
            However I think it's easier to do it here, since in the update function I have batch_size to deal with
            Although the replay buffer would have to hold more data by preprocessing and creating 2 new variables that 
            hold essentially the same info as state, and next_state, but just concatenated.
            '''
            full_state = np.concatenate((state[0], state[1]))
            full_next_state = np.concatenate((next_state[0], next_state[1]))

            buffer.add(state, full_state, actions_array, reward, next_state, full_next_state, done)

            state = next_state

            # update once after every episode_per_update
            if len(buffer) > batchsize and episode % episode_per_update == 0:
                for i in range(num_agents):
                    samples = buffer.sample()
                    maddpg.update(samples, i)
                maddpg.update_targets()  # soft update the target network towards the actual networks

            if np.any(done):
                #if any of the agents are done break
                break

        episode_reward = max(episode_reward_agent0, episode_reward_agent1)
        scores.append(episode_reward)
        scores_deque.append(episode_reward)
        avg_last_100.append(np.mean(scores_deque))
        # scores.append(episode_reward)
        print('\rEpisode {}\tAverage Score: {:.4f}\tScore: {:.4f}'.format(episode, avg_last_100[-1],
                                                                                        episode_reward),
              end="")

        if episode % PRINT_EVERY == 0:
            print('\rEpisode {}\tAverage Score: {:.4f}'.format(episode, avg_last_100[-1]))

        # saving successful model
        #training ends when the threshold value is reached.
        if avg_last_100[-1] >= threshold:
            save_dict_list = []

            for i in range(num_agents):
                save_dict = {'actor_params': maddpg.maddpg_agent[i].actor.state_dict(),
                             'actor_optim_params': maddpg.maddpg_agent[i].actor_optimizer.state_dict(),
                             'critic_params': maddpg.maddpg_agent[i].critic.state_dict(),
                             'critic_optim_params': maddpg.maddpg_agent[i].critic_optimizer.state_dict()}
                save_dict_list.append(save_dict)

                torch.save(save_dict_list,
                           os.path.join(model_dir, 'episode-{}.pt'.format(episode)))
            # plots graphs
            raw_score_plotter(scores)
            plotter(env_name, len(scores), avg_last_100, threshold)
            break

if __name__ == '__main__':
    main()
