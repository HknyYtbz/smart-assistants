from datetime import datetime
from math import sqrt

from sklearn.cross_validation import KFold
from scipy import stats as scipy_stats
import pandas
import numpy

from classifiers.metrics import QualityMetricsCalculator, runtime_metrics, quality_metrics
import plot

calculated_stats = ["Mean", "Std deviation", "Confidence interval"]

def confidence_interval(data, alpha=0.1):
    """
    Calculate the confidence interval for each column in a pandas dataframe.
    @param data: A pandas dataframe with one or several columns.
    @param alpha: The confidence level, by default the 90% confidence interval is calculated.
    @return: A series where each entry contains the confidence-interval for the corresponding column.
    """
    alpha = 0.1
    t = lambda column: scipy_stats.t.isf(alpha/2.0, len(column)-1)
    width = lambda column: t(column) * numpy.std(column.values, ddof=1)/sqrt(len(column))
    formatted_interval = lambda column: "%.2f +/- %.4f" % (column.mean(), width(column))
    return pandas.Series([formatted_interval(data[c]) for c in data.columns], index=data.columns)


class Experiment:

    def __init__(self, dataset):
        self.dataset = dataset
        self.classifiers = []
  
    def add_classifier(self, cls, name=None):
        if not name is None:
            cls.name = name
        self.classifiers.append(cls)

    def run_with_classifier(self, cls, data_for_folds):
        """
        @param data_for_folds: Contains one list of True/False values for each of the folds to be run. Each list states
                               for every item of the dataset, whether the item is in the current fold part of the
                               training dataset or the test dataset.
        @param cls: Classifier to use in the experiment.
        @return: Measurements for quality and runtime metrics.
        """
        runtimes = []
        quality = []
        for train, test in data_for_folds:

            #get the training and testing data for this fold
            data_train, data_test = self.dataset.data[train], self.dataset.data[test]
            target_train, target_test = self.dataset.target[train], self.dataset.target[test]

            #perform training
            train_time = datetime.now()
            cls = cls.fit(data_train, target_train)
            train_time = (datetime.now()-train_time).microseconds/1000.0

            #apply the classifier on the test data
            test_time = datetime.now()
            recommendations = cls.predict(data_test)
            test_time = (datetime.now()-test_time).microseconds/1000.0

            #add measurements for this replication to result collection
            runtimes.append({"Training time": train_time,
                             "Overall testing time": test_time,
                             "Individual testing time": test_time/float(len(data_test))})
            quality.append(QualityMetricsCalculator(target_test, recommendations).calculate())

        #calculate statistics over all replications
        return self.calculate_quality_stats(cls.name, quality), self.calculate_runtime_stats(cls.name, runtimes)

    def run(self, folds=10):
        """
        Run the experiment with all classifiers.
        @param folds: How many folds to run, perform 10-fold cross validation by default. folds must be >=2
        @return A `Results` object that can be used to print and plot experiment results.
        """
        assert(folds >= 2)

        #divide the data into the specified number of folds
        data_for_folds = KFold(len(self.dataset.data), n_folds=folds, indices=False)

        #run all of the classifiers and collect quality and runtime statistics
        stats = [self.run_with_classifier(cls, data_for_folds) for cls in self.classifiers]

        #group all quality stats in one big matrix, all runtime stats in another matrix
        quality_stats = pandas.concat([quality for quality, runtime in stats], axis=1)
        runtime_stats = pandas.concat([runtime for quality, runtime in stats])
        return Results(self.classifiers, quality_stats, runtime_stats)

    @staticmethod
    def calculate_quality_stats(cls_name, collected_measurements):
        #make a big matrix of all collected measurements over all replications and group according to the cutoff
        m = pandas.concat(collected_measurements)
        grouped = m.groupby(m.index)

        #calculate stats and rename columns to include name of the statistic and classifier,
        #e.g. Precision -> (Naive Bayes, Precision, Mean)
        map_column_names = lambda stat: {metric: (cls_name, metric, stat) for metric in quality_metrics}
        means = grouped.mean().rename(columns=map_column_names("Mean"))
        std = grouped.std().rename(columns=map_column_names("Std deviation"))
        conf = grouped.apply(confidence_interval).rename(columns=map_column_names("Confidence interval"))

        return pandas.concat([means, std, conf], axis=1)

    @staticmethod
    def calculate_runtime_stats(cls_name, collected_measurements):
        #make a big matrix of all collected measurements over all replications, no need to group anything here
        m = pandas.DataFrame(collected_measurements, columns=runtime_metrics)

        #calculate statistics, rename columns to include name of statistic, e.g. Training time -> (Training time, Mean)
        means = pandas.DataFrame(m.mean()).transpose()
        means.columns = [(metric, "Mean") for metric in runtime_metrics]
        std = pandas.DataFrame(m.std()).transpose()
        std.columns = [(metric, "Standard deviation") for metric in runtime_metrics]
        conf = pandas.DataFrame(confidence_interval(m)).transpose()
        conf.columns = [(metric, "Confidence interval") for metric in runtime_metrics]

        #put all individual statistics together and set name of classifier as index
        combined = pandas.concat([means, std, conf], axis=1)
        combined.index = [cls_name]
        return combined


class Results():

    def __init__(self, classifiers, quality_stats, runtime_stats):
        self.classifiers = classifiers
        self.quality_stats = quality_stats
        self.runtime_stats = runtime_stats

    def compare_quality(self, metric, statistic):
        """
        Grab results for given metric and statistic for all tested classifiers.
        @param metric: Name of one of the quality metrics.
        @param statistic: Which statistic to compare (Mean, Standard deviation, Confidence interval)
        @return: A pandas dataframe with one column for every classifier, listing the calculated statistics for the
        given metric and all cutoffs..
        """
        assert(statistic in calculated_stats)
        assert(metric in quality_metrics)

        relevant_columns = [(cls.name, metric, statistic) for cls in self.classifiers]
        new_column_names = [cls.name for cls in self.classifiers]
        comparison = self.quality_stats[relevant_columns]
        comparison = comparison.rename(columns={old: new for old, new in zip(relevant_columns, new_column_names)})
        return comparison

    #def compare_quality_at_cutoff(self, metric, statistics, cutoff):
        """
        Same as compare_classifiers, but only give results for the one selected cutoff, i.e. when the user is shown
        exactly #cutoff recommendations.
        @param metric: Name of one of the runtime or one of the quality metrics.
        @param statistics: Which statistic to compare (Mean, Standard deviation, Confidence interval)
        @param cutoff: The cutoff for which to print the results
        @return: A pandas dataframe with one row for every classifier and only one column with the calculated statistic
                 for the given metric at the given cutoff for each of the classifiers.
        """
    #    return pandas.DataFrame(self.compare_quality(metric, statistics).loc[cutoff], columns=[metric])

    def print_quality_comparison(self):
        """
        For each of the quality metrics, print a table of confidence intervals. One column for each tested classifier
        and one row for each tested recommendation cutoff. .
        @return:
        """
        for metric in quality_metrics:
            print "Results for %s" % metric
            print self.compare_quality(metric, "Confidence interval")

    """
    def print_quality_comparison_at_cutoff(self, cutoff):
        ""
        Print one shared table for all of the quality metrics. One row for each tested classifier, one column for each
        calculated runtime metric. Print only results for some given cutoff, i.e. when the user is shown  #cutoff
        recommendations.
        @param cutoff: The cutoff for which to print the results.
        @return:
        ""
        #statistics_for_cutoff = lambda metric: self.compare_quality_at_cutoff(metric, "Confidence interval", cutoff)
        #df = pandas.concat([pandas.DataFrame(statistics_for_cutoff(metric), columns=[metric])
        #                   for metric in quality_metrics], axis=1)
        #print df
        #print self.compare_quality_at_cutoff(cutoff)
    """

    def print_runtime_comparison(self):
        """
        Print one shared table of confidence intervals for all runtime metrics. One row for each tested classifier,
        one column for each calculated runtime metric.
        @return:
        """
        relevant_columns = [(metric, "Confidence interval") for metric in runtime_metrics]
        new_column_names = [metric for metric in runtime_metrics]
        comparison = self.runtime_stats[relevant_columns]
        comparison = comparison.rename(columns={old: new for old, new in zip(relevant_columns, new_column_names)})
        print comparison

    def plot_quality_comparison(self):
        """
        For each of the quality metrics, generate an XY-line-plot with one line for each classifier. The X-axis is the
        number of recommendations that are shown to the user, the Y-axis is the metric of interest. Uses the means of
        the measurements.
        @return:
        """
        for metric in quality_metrics:
            results = self.compare_classifiers(metric, "Mean")
            plot.plot_quality_comparison(results, metric, "../plots/houseA/%s.pdf" % metric)


