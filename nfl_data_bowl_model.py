# -*- coding: utf-8 -*-
"""NFL_DATA_BOWL_MODEL.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1UG0PMyL2oQCA1_WQulvB5AV--3oWAtMb

# Importing Data
- Imports and combines  weekly tracking data
- seperates the football tracking data to be used later
- Imports the plays data to be used later
"""

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

from sklearn.model_selection import train_test_split
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeClassifier

from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import AdaBoostRegressor

os.getcwd()
os.chdir('C:\\Users\\Ian Pakka\\Desktop')

tracking_9 = pd.read_csv("tracking_week_9.csv")
tracking_8 = pd.read_csv("tracking_week_8.csv")
tracking_7 = pd.read_csv("tracking_week_7.csv")
tracking_6 = pd.read_csv("tracking_week_6.csv")
tracking_5 = pd.read_csv("tracking_week_5.csv")
tracking_4 = pd.read_csv("tracking_week_4.csv")

combined_tracking_data = pd.concat([tracking_9, tracking_8, tracking_7, tracking_6, tracking_5, tracking_4])

# manipulatae plays in the left direction to assist the model in predicting loss of yards
combined_tracking_data.loc[combined_tracking_data['playDirection'] == 'left', 'x'] *= -1

FootballDf = combined_tracking_data.loc[combined_tracking_data['club'] == 'football']
FootballDf = FootballDf.loc[:, ["gameId","playId","frameId","x","y","s"]]

combined_tracking_data = combined_tracking_data[combined_tracking_data['club'].str.contains('football')==False]

plays = pd.read_csv("plays.csv")
pd.set_option('display.max_columns', 500)
plays["SUCCESSFUL PALY (> 3 yards"] = plays["playResult"].apply(lambda x: 1 if x > 3 else 0)
plays = plays.drop(plays[plays['playNullifiedByPenalty'] == "Y"].index)
plays["ballCarrierX"] = 0
plays["ballCarrierY"] = 0
plays.head()

plays_clean = plays[["gameId","playId","ballCarrierId","ballCarrierDisplayName","quarter","down","yardsToGo","possessionTeam","gameClock","playResult","playNullifiedByPenalty", "offenseFormation","defendersInTheBox",'absoluteYardlineNumber',"SUCCESSFUL PALY (> 3 yards"]]
plays_clean = plays_clean[plays_clean['playNullifiedByPenalty'].str.contains('Y')==False]

"""# Creating a dataframe for each team

- Allows us to look at the defense for just 1 team to prepare for them in a future game
- Selects desired features and removes unwanted plays
- Creates new features relevant to the analysis
"""

team_dfs = {}

for team in combined_tracking_data['club'].unique():

    # Filter the combined data to include only rows for the current team
    team_df = combined_tracking_data[combined_tracking_data['club'] == team]

    # Add the filtered DataFrame to the dictionary
    team_dfs[team] = team_df

# Create an empty dictionary to store the reshaped data
team_dfs_reshaped = {}

for team, team_df in team_dfs.items():
    # Reshape the DataFrame for the current team
    reshaped_df = team_df.groupby(['gameId', 'playId', 'frameId', 'club',"displayName"]).agg(
        X=('x', 'first'),
        Y=('y', 'first'),
        S=('s', 'first'),
        A=('a', 'first'),
        dis=("dis","first"),
        O=('o', "first"),
        playDirection=('playDirection', 'first'),
        event = ('event',"first")
    ).reset_index()

    # Sort the reshaped DataFrame by playId and frameId
    reshaped_df = reshaped_df.sort_values(['playId', 'frameId'])

    # Add the reshaped DataFrame to the new dictionary
    team_dfs_reshaped[team] = reshaped_df

team_dfs_reshaped_joined = {}

for team, team_df in team_dfs_reshaped.items():
    # Join the plays_clean DataFrame to the current team's reshaped DataFrame
    joined_df = team_df.merge(plays_clean, on=['gameId', 'playId'], how='left')

    # Filter out rows where team_dfs_reshaped["club"] == plays_clean["possessionTeam"]
    joined_df = joined_df[~(joined_df['club'] == joined_df['possessionTeam'])]

    # Sort the joined DataFrame by playId and frameId
    joined_df = joined_df.sort_values(['playId', 'frameId'])

    # Add the joined DataFrame to the new dictionary
    team_dfs_reshaped_joined[team] = joined_df

team_dfs_final = {}

for team, team_df in team_dfs_reshaped_joined.items():
    # Join the plays_clean DataFrame to the current team's reshaped DataFrame
    joined_df = team_df.merge(FootballDf, on=['gameId', 'playId', "frameId"], how='left')

    joined_df.loc[joined_df['playDirection'] == 'left', 'absoluteYardlineNumber'] *= -1

    # Add the joined DataFrame to the new dictionary
    team_dfs_final[team] = joined_df

team_dfs_final.keys()

Team_Inspect = "PIT"

"""# **Feature Engineering**
- creating variables such as distance to football and distance to line of scrimmage

"""

team_dfs_final[Team_Inspect]['event'] = team_dfs_final[Team_Inspect]['event'].fillna("NoEvent")

team_dfs_final[Team_Inspect]["disToFootball"] = team_dfs_final[Team_Inspect]['X'] - team_dfs_final[Team_Inspect]["x"]

team_dfs_final[Team_Inspect]["speedDiffToFootball"] = team_dfs_final[Team_Inspect]['S'] - team_dfs_final[Team_Inspect]["s"]

team_dfs_final[Team_Inspect]["disToLineOfScrimmage"] = team_dfs_final[Team_Inspect]['X'] - team_dfs_final[Team_Inspect]["absoluteYardlineNumber"]

team_dfs_final[Team_Inspect]

"""# **Filtering to only run plays**"""

test = team_dfs_final[Team_Inspect].groupby("playId").event.unique()
test = pd.DataFrame(test)
test = test.reset_index()

filtered_playIds = []

for index, row in test.iterrows():
    if not (test["event"][index] == "handoff").any():
        filtered_playIds.append(test["playId"][index])

print(f"Play IDs without 'handoff': {filtered_playIds}")

team_dfs_final[Team_Inspect] = team_dfs_final[Team_Inspect][~team_dfs_final[Team_Inspect]['playId'].isin(filtered_playIds)]

"""# **TRAIN TEST SPLIT**
- Could not use standard train_test_split due to data leakage
- As of now we are only standardizing the X feaature
"""

unique_ids = {}

for i in team_dfs_final.keys():

  unique_ids[i] = team_dfs_final[i]["playId"].unique()

# set np random seed
np.random.seed(1)

# Calculate the number of elements to select (80% of the array)
num_elements_to_select = int(0.8 * len(unique_ids[Team_Inspect]))

# Generate random indices to select
random_indices = np.random.choice(len(unique_ids[Team_Inspect]), num_elements_to_select, replace=False)

# Select the elements based on the random indices
training_ids = unique_ids[Team_Inspect][random_indices]
testing_ids = np.setdiff1d(unique_ids[Team_Inspect], training_ids)

X_train = team_dfs_final[Team_Inspect].where(team_dfs_final[Team_Inspect]["playId"].isin(training_ids))
X_train.dropna(inplace = True)
y_train = team_dfs_final[Team_Inspect]["playResult"].where(team_dfs_final[Team_Inspect]["playId"].isin(training_ids))
y_train.dropna(inplace = True)

X_test = team_dfs_final[Team_Inspect].where(team_dfs_final[Team_Inspect]["playId"].isin(testing_ids))
X_test.dropna(inplace = True)
y_test = team_dfs_final[Team_Inspect]["playResult"].where(team_dfs_final[Team_Inspect]["playId"].isin(testing_ids))
y_test.dropna(inplace = True)
y_test_preds = team_dfs_final[Team_Inspect][["playId","frameId","playResult"]].where(team_dfs_final[Team_Inspect]["playId"].isin(testing_ids))
y_test_preds.dropna(inplace = True)
y_train_preds = team_dfs_final[Team_Inspect][["playId","frameId","playResult"]].where(team_dfs_final[Team_Inspect]["playId"].isin(training_ids))
y_train_preds.dropna(inplace = True)

preds_df = X_train

X_train_encoded = pd.concat([X_train, pd.get_dummies(X_train["event"]).astype(np.int8)], axis=1)
X_test_encoded = pd.concat([X_test, pd.get_dummies(X_test["event"]).astype(np.int8)], axis=1)

X_train_encoded = pd.concat([X_train_encoded, pd.get_dummies(X_train["offenseFormation"]).astype(np.int8)], axis=1)
X_test_encoded = pd.concat([X_test_encoded, pd.get_dummies(X_test["offenseFormation"]).astype(np.int8)], axis=1)

sc = StandardScaler()

ct = ColumnTransformer([('scaler', sc, [5])])

X_train_transformed = ct.fit_transform(X_train)
X_test_transformed = ct.transform(X_test)

X_train_encoded["X"] = X_train_transformed
X_test_encoded["X"] = X_test_transformed

X_train = X_train_encoded[["X","S","disToFootball","speedDiffToFootball","yardsToGo","disToLineOfScrimmage"]]
X_test = X_test_encoded[["X","S","disToFootball","speedDiffToFootball","yardsToGo","disToLineOfScrimmage"]]

X_train.shape

"""# Gradient Boosting Regressor

- uses 1 teams dataframe

- predicts playResult

- New model should be trained and tuned to provide most  accurate results for that team. If we used all the data we may be able to gain more general insights to NFL defenses. However, I believe this model would be more useful on a week to week basis to prepare and offensive run game against a specific team.
"""

params = {'learning_rate':[0.05]}

CLF = GridSearchCV(GradientBoostingRegressor(random_state=99,n_estimators=1000,max_depth=3,max_features = 5,alpha = 0.1),params,cv = 5, scoring = "neg_mean_absolute_error")
CLF.fit(X_train,y_train)

preds = CLF.best_estimator_.predict(X_train)
print(CLF.best_score_)
print(mean_absolute_error(y_train, preds))
print(mean_squared_error(y_train, preds))

Importance = pd.DataFrame({'Importance':CLF.best_estimator_.feature_importances_*100}, index=X_train.columns)
Importance.sort_values(by='Importance', axis=0, ascending=True).plot(kind='barh', color='r', )
plt.xlabel('Variable Importance')
plt.gca().legend_ = None

plt.scatter(preds, y_train)
plt.plot([0, 1], [0, 1], '--k', transform=plt.gca().transAxes)

# Used to create below chart which may gives a better picture as to how accurate we are on a play level rather than framae level
preds_df["Predictions"] = preds

plt.scatter(preds_df["Predictions"].groupby(preds_df["playId"]).mean(), y_train_preds["playResult"].groupby(preds_df["playId"]).mean())
plt.plot([0, 1], [0, 1], '--k', transform=plt.gca().transAxes)

"""# Visualizations / data saving

- Save predictions to create visualizations

"""

preds_df_summary = preds_df.groupby(['gameId', 'playId', 'frameId',"displayName"]).agg(
        Predictions = ('Predictions', 'first'),
        playResult = ('playResult',"mean"))

preds_df_summary["Predictions average per play"] = preds_df.groupby(['gameId', 'playId','frameId']).agg(
        Predictions=('Predictions', 'mean'))

file_path = "C:/Users/Ian_Pakka/Downloads/data.csv"
preds_df.to_csv(file_path, index = False)