# -*- coding: UTF-8 -*-
"""
This module contains some additional functions for exploring the data and the recommendation results produced
by the different classifiers.
"""

import os
import datetime

import pandas

from classifiers.bayes import NaiveBayesClassifier
from classifiers.temporal import TemporalEvidencesClassifier
from classifiers.binning import initialize_bins
from experiment import plot
from experiment.metrics import QualityMetricsCalculator
from experiment.experiment_framework import delta_in_ms
from dataset import load_dataset_as_sklearn


#store plots in ../plots/
plot_directory = os.path.join(os.pardir, "plots")
img_type = "pdf"


def plot_observations(data):
    """
    Show which actions typically follow a given user action.
    @param data: The dataset for which to plot the observations.
    """
    """
    Note: the figure for "Frontdoor=Closed" slightly deviates from Figure 1 in the paper and Figure 5.1 in the
    dissertation (see paper_experiments.py for bibliographical information). The number of observed actions was reported
    correctly in the paper/dissertation, however there was an issue with ordering which actions occur most commonly,
    which resulted in "Open cups cupboard" being erroneously included in the figure. Despite this issue, the main point
    of the figure still stands: the user has some observable habits after closing the frontdoor.
    """
    def observations_as_dataframe(counts, bins):
        obs = pandas.DataFrame(counts)
        obs.columns = data.target_names
        obs.index = bins
        return obs

    cls = TemporalEvidencesClassifier(data.features, data.target_names, bins=initialize_bins(0, 300, 10))
    cls = cls.fit(data.data, data.target)

    conf = plot.plot_config(plot_directory, sub_dirs=[data.name, "observations"], img_type=img_type)
    for source in cls.sources.values():
        observations = observations_as_dataframe(source.temporal_counts, cls.binning_method.bins)
        plot.plot_observations(source.source_name(), observations, conf)


def confusion_matrix(data):
    """
    Print a confusion matrix: for each action contains information on how often each service was recommended
    @param data: The dataset for which to print the matrix,
    @return:
    """

    cls = TemporalEvidencesClassifier(data.features, data.target_names)
    #cls = RandomClassifier(data.features, data.target_names)

    time = datetime.datetime.now()
    cls = cls.fit(data.data, data.target)
    time = datetime.datetime.now() - time
    #print delta_in_ms(time)

    time = datetime.datetime.now()
    results = cls.predict(data.data)
    time = datetime.datetime.now() - time
    #print delta_in_ms(time)
    #print delta_in_ms(time)/len(data.data)

    """
    matrix = QualityMetricsCalculator(data.target, results).confusion_matrix()

    #for pretty printing purposes, replace name of recommendation in columns with single letter,
    #and have row index "(letter) action"
    letters = list(map(chr, list(range(97, 123))))+list(map(chr, list(range(65, 91))))
    action_to_letter = {action: letter for action, letter in zip(matrix.index, letters)}
    matrix.columns = [action_to_letter[action] for action in matrix.columns]
    matrix.index = ["(%s) %s" % (action_to_letter[action], action) for action in matrix.index]
    matrix.index.name = "Actual action"

    pandas.set_option('expand_frame_repr', False)
    pandas.set_option('max_columns', 40)
    print matrix
    """


def histogram_compare_methods(data):
    """
    Create a histogram that compares true positives for different classifiers/classifier settings
    @param data: The dataset for which to create the plot.
    """

    classifiers = [NaiveBayesClassifier(data.features, data.target_names),
                   TemporalEvidencesClassifier(data.features, data.target_names)]

    #run the experiment using full dataset as training and as test data
    results = []
    for cls in classifiers:
        cls = cls.fit(data.data, data.target)
        r = cls.predict(data.data)
        r = QualityMetricsCalculator(data.target, r)
        results.append(r.true_positives_for_all())

    #want for each classifier result only the measurements for cutoff=1
    results = [r.loc[1] for r in results]
    results = pandas.concat(results, axis=1)
    results.columns = [cls.name for cls in classifiers]

    conf = plot.plot_config(plot_directory, sub_dirs=[data.name], prefix="compare_methods_", img_type=img_type)
    plot.comparison_histogram(results, conf)


def histogram_compare_cutoffs(data):
    """
    Create a histogram that compares true positives for different cutoffs using one classifier.
    @param data: The dataset for which to create the plot.
    """

    to_compare = [1, 2, 3, 4]

    #run classifier and count true positives
    cls = TemporalEvidencesClassifier(data.features, data.target_names)
    cls = cls.fit(data.data, data.target)
    results = cls.predict(data.data)
    results = QualityMetricsCalculator(data.target, results).true_positives_for_all()

    #only use the interesting cutoffs
    results = results.transpose()[to_compare]
    results.columns = ["cutoff=%s" % c for c in results.columns]

    conf = plot.plot_config(plot_directory, sub_dirs=[data.name], prefix="compare_cutoffs_", img_type=img_type)
    plot.comparison_histogram(results, conf)


dataset = load_dataset_as_sklearn("../datasets/houseA.csv", "../datasets/houseA.config")
#dataset = load_dataset_as_sklearn("../datasets/houseB.csv",)

#Show which actions typically follow a given user action.
plot_observations(dataset)
#confusion_matrix(dataset)
#histogram_compare_methods(dataset)
#histogram_compare_cutoffs(dataset)
