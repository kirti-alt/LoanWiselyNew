import os, joblib, pickle, numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'trained_model', 'loan_model.pkl')
FEATURES_PATH = os.path.join(os.path.dirname(__file__), '..', 'trained_model', 'model_features.pkl')

def load_model():
    model, features = None, None
    if os.path.exists(MODEL_PATH):
        try:
            model = joblib.load(MODEL_PATH)
        except:
            with open(MODEL_PATH, 'rb') as f:
                model = pickle.load(f)
    if os.path.exists(FEATURES_PATH):
        with open(FEATURES_PATH, 'rb') as f:
            features = pickle.load(f)
    return {'model': model, 'features': features}

def _prepare_input(feature_list, data):
    x = []
    for f in feature_list:
        v = data.get(f, data.get(f.lower(), data.get(f.upper(), '')))
        if isinstance(v, str) and v.strip().isdigit():
            v = float(v)
        x.append(v)
    return x

def predict_from_model(loaded, data):
    model, features = loaded.get('model'), loaded.get('features')
    if features is None:
        features = ['Married','Gender','Dependents','Education','Self_Employed',
                    'ApplicantIncome','CoapplicantIncome','LoanAmount','Loan_Amount_Term',
                    'CreditScore','Property_Area','Age']
    x = _prepare_input(features, data)
    try:
        arr = np.array(x, dtype=object).reshape(1, -1)
        pred = model.predict(arr)[0]
        eligible = bool(pred)
        try:
            prob = model.predict_proba(arr)[0][1]
        except:
            prob = 0.75 if eligible else 0.25
        return {'eligible': eligible, 'probability': float(prob)}
    except:
        credit = float(data.get('CreditScore', 0))
        income = float(data.get('ApplicantIncome', 0))
        eligible = credit >= 600 and income >= 15000
        return {'eligible': eligible, 'probability': 0.5}
