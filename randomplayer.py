from pypokerengine.players import BasePokerPlayer
import numpy as np
import random
from collections import deque
from sklearn.preprocessing import LabelEncoder
from sklearn.preprocessing import OneHotEncoder
from keras.layers import Dense, SimpleRNN
from keras.models import Sequential
from keras.optimizers import Adam
from keras import backend as K
import pypokerengine.utils.game_state_utils as gsu

class RandomPlayer(BasePokerPlayer):

    def __init__(self):	
        super(RandomPlayer, self).__init__()	
        STATE_SIZE = 125	
        N_ACTIONS = 8	
        N_AGENTS = 4 # default	
        STARTING_EPSILON = 1.0 # default	
        E_MIN = 0.01	
        E_DECAY = 0.995	
        GAMMA = 0.95	

        init_stack_size = 1000	

        self.agent = DQNAgent(STATE_SIZE, N_ACTIONS, N_AGENTS, STARTING_EPSILON, E_MIN, E_DECAY, GAMMA)	
        self.agent.load("trainedModel2.h5")	

    def declare_action(self, valid_actions, hole_card, round_state):

        features = self.agent.make_features(valid_actions, hole_card, round_state)
        actions = self.agent.act(features)

        sorted_by_best_action = np.argsort(actions)[::-1]
        chosen_action = sorted_by_best_action[0]
        action = None

        if chosen_action == 0:
            action = 'fold'
        elif chosen_action == 1:
            action = 'call'
        else:
            action = 'raise'

        return action

    def receive_game_start_message(self, game_info):
        # print("\n\n")
        # pprint.pprint(game_info)
        # print("---------------------------------------------------------------------")
        pass

    def receive_round_start_message(self, round_count, hole_card, seats):
        # print("My ID : "+self.uuid+", round count : "+str(round_count)+", hole card : "+str(hole_card))
        # pprint.pprint(seats)
        # print("-------------------------------")
        pass

    def receive_street_start_message(self, street, round_state):
        pass

    def receive_game_update_message(self, action, round_state):
        pass

    def receive_round_result_message(self, winners, hand_info, round_state):
        # print("My ID (round result) : "+self.uuid)
        # pprint.pprint(round_state)
        # print("\n\n")
        # self.round_count = self.round_count + 1
        pass

    def setup_ai():
        return RandomPlayer()

def _explode_array(array):
    return [[a] for a in array]

"""
One Hot Encoding is the representation of categorical variables as binary vectors
"""
SUIT_TO_INT_ENC = LabelEncoder().fit(['H', 'S', 'D', 'C'])
SUIT_INT_TO_ONEHOT_ENC = OneHotEncoder(sparse=False).fit(_explode_array(range(0, 4)))
VALUE_INT_TO_ONEHOT_ENC = OneHotEncoder(sparse=False).fit(_explode_array(range(2, 15)))
MEMORY = deque()

def suits_to_onehot(suits):
    def _suits_to_ints(suits):
        return SUIT_TO_INT_ENC.transform(_explode_array(suits))

    def _suit_ints_to_onehot(suits):
        return SUIT_INT_TO_ONEHOT_ENC.transform(_explode_array(suits))

    return _suit_ints_to_onehot(_suits_to_ints(suits))

def card_values_to_onehot(values):
    return VALUE_INT_TO_ONEHOT_ENC.transform(_explode_array(values))

def clear_memory():
    MEMORY.clear()

class DQNAgent:
    def __init__(self, state_size, action_size, num_agents, starting_epsilon, e_min, e_decay, gamma):
        self.state_size = state_size
        self.action_size = action_size
        self.num_agents = num_agents
        """
        Usually, the value of Epsilon decreases over time,
        it can be modelled by epsilon = (n+1)** -0.5
        In this case, the Epsilon decreases in this manner: e *= epsilon_decay per round of execution.
        Epsilon is lower bounded by epsilon_min
        Epsilon decreases as we want to explore more in the early stages and exploit more in the later stages
        """
        self.epsilon = starting_epsilon  # exploration rate, See epsilon-greedy policy.
        self.epsilon_min = e_min
        self.epsilon_decay = e_decay
        """
        discount rate is used in calculating the total gain for any given action-state pair.
        
        G(s,a) = Expectation[Reward(s+1) + gamma*G(s+1, a+1) | State = s, Action = a] 
        Note that G(s,a) is recursively defined, so gamma compounds for future gains.
        """
        self.gamma = gamma  # discount rate

        self.learning_rate = 0.001
        self.model = self._build_model()

    def _build_model(self):
        # Neural Net for Deep-Q learning Model
        model = Sequential()
        model.add(SimpleRNN(64, input_shape=(1, self.state_size), activation='relu', return_sequences=True))
        model.add(SimpleRNN(32, activation='relu'))
        # model.add(Dense(64, activation='relu'))
        # model.add(Dense(64, activation='relu'))
        model.add(Dense(self.action_size, activation='linear'))
        # Note: MSE = Mean Squared Error
        model.compile(loss='mse',       # if you change this, make sure to change it in set_model
                      optimizer=Adam(lr=self.learning_rate))
        return model

    def remember(self, state, action, reward, next_state, done):
        """
        This is used later on for experience replay
        (s, a, r, s', is_terminal)
        :param state:
        :param action:
        :param reward:
        :param next_state:
        :param done:
        :return:
        """
        MEMORY.append((state, action, reward, next_state, done))

    def act(self, state):
        state = state.reshape((1, 1, len(state)))
        """
        Exploration is triggered if rand is less than epsilon
        """
        if np.random.rand() <= self.epsilon:
            return np.random.uniform(low=-10, high=10, size=(self.action_size,))

        """
        else, exploitation
        """
        act_values = self.model.predict([state])[0]
        return act_values  # returns action

    def replay(self, batch_size):
        """
        Note that the target here refers to the calculated quality/gain/reward from the target policy
        :param batch_size:
        :return:
        """
        if batch_size > len(MEMORY):
            return
        # Sample random minibatch of transitions from MEMORY
        minibatch = random.sample(MEMORY, batch_size)
        for state, action, reward, next_state, done in minibatch:
            if state is None:
                continue
            state = state.reshape((1,1,len(state)))
            target = reward
            """
            If non-terminal,
            set target = current_reward + discount_rate + arg_max{a`}(Expectation of Q(next_state, a`))
            """
            if not done:
                next_state = next_state.reshape((1,1,len(next_state)))
                # target = {r + gamma * argmax_a[Q(s,a)]}
                target = (reward + self.gamma *
                          np.amax(self.model.predict(next_state)[0]))
            """
            Else (terminal), target = current_reward
            """
            target_f = self.model.predict(state)
            target_f[0][action] = target
            """
            Perform ONE gradient descent step on state(training), target_f(label)
            """
            self.model.fit(state, target_f, epochs=1, verbose=0)
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def load(self, name):
        self.model.load_weights(name)

    def save(self, name):
        self.model.save_weights(name)

    def clear_session(self):
        K.clear_session()

    def make_features(self, valid_actions, hole_cards, game_state):
        player_idx = game_state['next_player']
        player_uuid = game_state['seats'][player_idx]['uuid']
        bb_amount = game_state['small_blind_amount'] * 2

        # split hole cards, onehot suits and values

        hole_suits, hole_values = self._cards_to_arrays(hole_cards)
        hole_suits = suits_to_onehot(hole_suits)
        hole_values = card_values_to_onehot(hole_values)

        # river cards
        temp_suit_zeros = np.zeros((5, 4))
        temp_value_zeros = np.zeros((5, 13))
        river_suits, river_values = self._cards_to_arrays(game_state['community_card'])
        if river_suits and river_values:
            river_suits = suits_to_onehot(river_suits)
            river_values = card_values_to_onehot(river_values)
            temp_suit_zeros[:river_suits.shape[0], :river_suits.shape[1]] = river_suits # 0-padding
            temp_value_zeros[:river_values.shape[0], :river_values.shape[1]] = river_values

        river_suits = temp_suit_zeros
        river_values = temp_value_zeros

        # pot
        total_pot_as_bb = [game_state['pot']['main']['amount'] / bb_amount]

        # own stack size
        own_stack_size = [game_state['seats'][player_idx]['stack'] / bb_amount]

        # other players stack size
        players_after_stacks = [p['stack'] / bb_amount for p in game_state['seats'][player_idx + 1:]]
        players_before_stacks = [p['stack'] / bb_amount for p in game_state['seats'][:player_idx]]
        players_after_stacks.extend(players_before_stacks)
        other_players_stack_sizes = players_after_stacks

        # TODO: distance from button, scaled from 0 to 1
        # n_players = len(game_state['seats'])
        # distance = ()

        # players folded? (binary)
        players_after_folds = [int(p['state'] == 'folded') for p in game_state['seats'][player_idx + 1:]]
        players_before_folds = [int(p['state'] == 'folded') for p in game_state['seats'][:player_idx]]
        players_after_folds.extend(players_before_folds)
        player_folds = players_after_folds

        # action history, for use below
        game_state_histories = (game_state['action_histories'].values())
        action_history = [action for phase in game_state_histories for action in phase]

        # money put into pot by each player since our last
        moves_since_our_last = []
        for action in action_history[::-1]:
            if action['uuid'] != player_uuid:
                moves_since_our_last.append(action)
            else:
                break
        moves_since_our_last.reverse()
        moves_since_our_last = moves_since_our_last[:self.num_agents]
        temp_move_zeroes = np.zeros(self.num_agents)
        money_since_our_last_move = [a.get('amount', 0) for a in moves_since_our_last]
        for i, m in enumerate(money_since_our_last_move):
            temp_move_zeroes[i] = m
        money_since_our_last_move = temp_move_zeroes

        feature_arrays = [hole_values, hole_suits, river_values, river_suits, total_pot_as_bb,
                own_stack_size, other_players_stack_sizes, player_folds, money_since_our_last_move
                ]

        ret = None

        for array in feature_arrays:
            array = np.array(array).flatten()
            if ret is not None:
                ret = np.concatenate((ret, array))
            else:
                ret = array

        return ret

    def _cards_to_arrays(self, cards):
        suits = []
        values = []
        for card in cards:
            if card[1:] == 'A': card = card[0] + '14'
            if card[1:] == 'K': card = card[0] + '13'
            if card[1:] == 'Q': card = card[0] + '12'
            if card[1:] == 'J': card = card[0] + '11'
            if card[1:] == 'T': card = card[0] + '10'
            suits.append(card[0])
            values.append(int(card[1:]))
        return suits, values

    def set_model(self, model, weights):
        self.model = model
        self.model.set_weights(weights)
        self.model.compile(loss='mse',
                           optimizer=Adam(lr=self.learning_rate))

    def get_init_info(self):
        '''Return info as array. Easy to use to reinstantiate the agent'''
        info = [
            self.state_size,
            self.action_size,
            self.num_agents,
            self.epsilon,
            self.epsilon_min,
            self.epsilon_decay,
            self.gamma
        ]
        return info
