#!/usr/bin/env python
# coding: utf-8

# In[45]:


import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from tqdm import tqdm
import cricketstats as cks


# In[46]:


database ="../data/raw/all_json.zip"


# In[47]:


def data_extracter(matchtype, from_date, to_date):
    search = cks.cricketstats.search(allplayers=True)
    # Optional Arguments:
    # First we can set overs and innings related arguments:
    betweenovers=[] # Search only these overs. eg. betweenovers = [1, 20]. Or if you only want to search for powerplays that are mandatory and option input "powerplays" eg. betweenovers =["powerplays"]
    innings=[] # Search these innings. Options: 1, 2, 3, 4 eg. innings = [1,3]
    fielders=[] # Search bowling stats involves these fielders.
    oppositionbatters=[] # Search overs where players have bowled against certain batters. Options: batter names. You can also put in a list of batters by handedness. eg. oppositionbatters=["Left hand", "Right Hand"]
    oppositionbowlers=[] # Search overs where players have batted against certain bowlers Options: bowler names You can also put in list of bowlers by type, eg. oppositionbowlers=["Right arm pace","Left arm pace","Right arm Off break","Right arm Leg break","Left arm orthodox","Left arm wrist spin"]
    superover=None # Search normal innings or superover innings. Options: True, False eg. superover=True
    battingposition=[] # Search stats at certain position in batting order. eg. battingposition=[1,2,3]
    bowlingposition=[] # Search stats at certain position in bowling order. eg. bowlingposition=[1,2]
    
    # Second we have match related arguments
    sex=[] # Search only matches of certain sex. Options: "male", "female" eg. sex = ["female"] 
    playerteams=[] # Search matches where players have played in certain teams. Options: team names eg. playerteams=["Australia", "England"]
    teammates=[] # Search matches where certain teammates play. For this to work playerteams must be populated.
    oppositionteams=[] # Search matches where opposition is only certain teams. Options: team names eg. oppositionteams=["India", "England"]
    venue=[] # Search matches played only at these venues Options: Cricket Grounds eg. venue=["Sydney Cricket Ground", "Melbourne Cricket Ground", ""Brisbane Cricket Ground, Woolloongabba""]
    teamtype=[] # Search only for particualr type of teams. eg. "international", "club".
    event=[] # Search matches played as part of these Leagues or Tournaments Options: Name of League or Tournament eg. event=["Sheffield Shield", "ICC World Cup", "Big Bash League"] 
    matchresult=None # Search matches where players or teams have these results. When looking at players, this option **must** be used with at one team in playersteams variable. Options either "won" or "loss" or "draw" or "tie" eg. matchresult="won"
    sumstats=False # When switched to True, it adds an "all players" or "all teams" row at end of result that sums all players or teams stats that are searched for.
    search.stats(database, from_date, to_date, matchtype, betweenovers=betweenovers, innings=innings, sex=sex, playersteams=playerteams, oppositionbatters=oppositionbatters, oppositionbowlers=oppositionbowlers, oppositionteams=oppositionteams, venue=venue, event=event, matchresult=matchresult, superover=superover, battingposition=battingposition, bowlingposition=bowlingposition, fielders=fielders, sumstats=sumstats)
    data_var = "_".join(matchtype)+"_data" 
    globals()[data_var] = search.inningsresult
    globals()[data_var].to_csv(f"../data/raw/{data_var}.csv")


# In[5]:


from_date = (2010, 1, 1)
to_date = (2026, 5, 31) # The (Year, Month, Day) from which to end search
matchtype = ["Test", "MDM"] # Options: ["Test", "MDM", "ODI", "ODM", "T20", "IT20"] Explanation of what these mean is found at https://cricsheet.org/downloads/
# matchtype = ["T20", "IT20" ] # Options: ["Test", "MDM", "ODI", "ODM", "T20", "IT20"] Explanation of what these mean is found at https://cricsheet.org/downloads/
data_extracter(matchtype,from_date,to_date)


# In[34]:


from_date = (2010, 1, 1)
to_date = (2026, 5, 31) # The (Year, Month, Day) from which to end search
matchtype = ["T20" ] # Options: ["Test", "MDM", "ODI", "ODM", "T20", "IT20"] Explanation of what these mean is found at https://cricsheet.org/downloads/
# matchtype = ["T20", "IT20" ] # Options: ["Test", "MDM", "ODI", "ODM", "T20", "IT20"] Explanation of what these mean is found at https://cricsheet.org/downloads/
data_extracter(matchtype,from_date,to_date)


# In[ ]:


from_date = (2010, 1, 1)
to_date = (2026, 5, 31) # The (Year, Month, Day) from which to end search
matchtype = ["ODI", "ODM" ] # Options: ["Test", "MDM", "ODI", "ODM", "T20", "IT20"] Explanation of what these mean is found at https://cricsheet.org/downloads/
# matchtype = ["T20", "IT20" ] # Options: ["Test", "MDM", "ODI", "ODM", "T20", "IT20"] Explanation of what these mean is found at https://cricsheet.org/downloads/
data_extracter(matchtype,from_date,to_date)


# In[48]:


import pandas as pd

_original_DataFrame = pd.DataFrame

def debug_df(data=None, *args, **kwargs):
    if isinstance(data, dict):
        lens = {}
        for k, v in data.items():
            try:
                lens[k] = len(v)
            except:
                pass

        if len(set(lens.values())) > 1:
            print("\nMISMATCH FOUND:\n")
            for k, v in sorted(lens.items()):
                print(k, v)

    return _original_DataFrame(data, *args, **kwargs)

pd.DataFrame = debug_df


# In[49]:


data_extracter(["IT20"], (2010,1,1), (2026,5,31))

