
def best_x_predictions(predictions,x):
    ordered=sorted(predictions.items(),key=lambda (element,mass):mass,reverse=True)
    return {key:value for (key,value) in ordered[0:x]}

def dynamic_cutoff(max_conflict,max_theta,cutoff):
    def perform(predictions,conflict,theta):
        if conflict<max_conflict and theta<max_theta:
            return best_x_predictions(predictions,cutoff)
        else:
            return predictions          
    return perform
