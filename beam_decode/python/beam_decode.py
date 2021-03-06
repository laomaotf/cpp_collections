"""
Author: Awni Hannun
This is an example CTC decoder written in Python. The code is
intended to be a simple example and is not designed to be
especially efficient.
The algorithm is a prefix beam search for a model trained
with the CTC loss function.
For more details checkout either of these references:
  https://distill.pub/2017/ctc/#inference
  https://arxiv.org/abs/1408.2873
"""

import numpy as np
import math
import collections
import yaml,cv2

NEG_INF = -float("inf")


# 创建一个新的beam
def make_new_beam():
    fn = lambda: (NEG_INF, NEG_INF)
    return collections.defaultdict(fn)


# 概率乘法
# 因为代码中为了避免数据下溢，都采用的是对数概率，所以看起来比较繁琐
def logsumexp(*args):
    """
    Stable log sum exp.
    """
    if all(a == NEG_INF for a in args):
        return NEG_INF
    a_max = max(args)
    lsp = math.log(sum(math.exp(a - a_max) for a in args))
    return a_max + lsp


def beam_decode(probs, beam_size=1, blank=0):
    """
    Performs inference for the given output probabilities.
    Arguments:
      probs: The output probabilities (e.g. post-softmax) for each
        time step. Should be an array of shape (time x output dim).
      beam_size (int): Size of the beam to use during inference.
      blank (int): Index of the CTC blank label.
    Returns the output label sequence and the corresponding negative
    log-likelihood estimated by the decoder.
    """
    # T表示时间，S表示词表大小
    T, S = probs.shape

    # Elements in the beam are (prefix, (p_blank, p_no_blank))
    # Initialize the beam with the empty sequence, a probability of
    # 1 for ending in blank and zero for ending in non-blank
    # (in log space).
    # 每次总是保留beam_size条路径

    beam = [(tuple(), (0.0, NEG_INF))]

    for t in range(T):  # Loop over time

        # A default dictionary to store the next step candidates.
        next_beam = make_new_beam()  #t时刻重新构造一批beam

        for s in range(S):  # Loop over vocab
            p = probs[t, s] #遍历t时刻所有symbol
           # print(t, '-', s)
            # The variables p_b and p_nb are respectively the
            # probabilities for the prefix given that it ends in a
            # blank and does not end in a blank at this time step.
            for prefix, (p_b, p_nb) in beam:  # 遍历已有的beam，每个beam记录三项(当前字符prefix, 以blank结尾的概率p_b, 以非blank结束的概率p_nb)
                # p_b表示前缀最后一个是blank的概率，p_nb是非blank的概率
                # If we propose a blank the prefix doesn't change.
                # Only the probability of ending in blank gets updated.
                if s == blank:
                    # 增加的字母是blank
                    # n_p_b和n_p_nb第一n表示new是新创建的路径
                    n_p_b, n_p_nb = next_beam[prefix]
                    n_p_b = logsumexp(n_p_b, p_b + p, p_nb + p) #如果当前symbol是blank,则新beam的p_b概率等于三个概率的乘积
                    next_beam[prefix] = (n_p_b, n_p_nb)
                    continue

                # Extend the prefix by the new character s and add it to
                # the beam. Only the probability of not ending in blank
                # gets updated.
                end_t = prefix[-1] if prefix else None
                n_prefix = prefix + (s,)
                n_p_b, n_p_nb = next_beam[n_prefix]
                if s != end_t:
                    # 如果s不和上一个不重复，则更新非空格的概率
                    n_p_nb = logsumexp(n_p_nb, p_b + p, p_nb + p)
                else:
                    # 如果s和上一个重复，也要更新非空格的概率
                    # We don't include the previous probability of not ending
                    # in blank (p_nb) if s is repeated at the end. The CTC
                    # algorithm merges characters not separated by a blank.
                    n_p_nb = logsumexp(n_p_nb, p_b + p)

                # *NB* this would be a good place to include an LM score.
                next_beam[n_prefix] = (n_p_b, n_p_nb)

                # If s is repeated at the end we also update the unchanged
                # prefix. This is the merging case.
                if s == end_t:
                    n_p_b, n_p_nb = next_beam[prefix]
                    n_p_nb = logsumexp(n_p_nb, p_nb + p)
                    next_beam[prefix] = (n_p_b, n_p_nb)

        # Sort and trim the beam before moving on to the
        # next time-step.
        # 根据概率进行排序，每次保留概率最高的beam_size条路径
        beam = sorted(next_beam.items(),
                      key=lambda x: logsumexp(*x[1]), 
                      reverse=True)
        beam = beam[:beam_size]

    best = beam[0]
    return best[0], -logsumexp(*best[1])


if __name__ == "__main__":
    np.random.seed(3)

    time = 10
    output_dim = 5

    probs = np.random.rand(time, output_dim)
    probs = probs / np.sum(probs, axis=1, keepdims=True)

    fs = cv2.FileStorage("data.yml",cv2.FILE_STORAGE_READ)    
    probs =	fs.getNode("prob").mat()
    fs.release()


    labels, score = beam_decode(probs)
    print(labels)
    print("Score {:.3f}".format(score))