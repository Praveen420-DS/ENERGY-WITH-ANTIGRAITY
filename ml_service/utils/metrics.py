from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

class Metrics:
    @staticmethod
    def mae(y_true, y_pred):
        return mean_absolute_error(y_true, y_pred)

    @staticmethod
    def rmse(y_true, y_pred):
        return mean_squared_error(y_true, y_pred, squared=False)

    @staticmethod
    def r2(y_true, y_pred):
        return r2_score(y_true, y_pred)
