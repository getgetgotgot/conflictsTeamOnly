import streamlit as st
import plotly.express as px
import pandas as pd
import scipy as stats
country_coverage = pd.read_csv('C://Users//Ana//Downloads//coverage_with_scores_filter.csv')


st.title("April 2026 Conflict Invisibility Preliminary Analysis")

fig = px.scatter(country_coverage, 
                 x='z_fatality', 
                 y='z_articles',
                 color='invisibility_score',
                 size='total_deaths',  # or use a constant
                 hover_name='country',
                 color_continuous_scale='RdBu_r',
                 labels={'z_fatality': 'Z-score Fatalities', 
                        'z_articles': 'Z-score Articles',
                        'invisibility_score': 'Invisibility Score (z-scored)'})

fig.update_traces(marker=dict(size=12))  
st.plotly_chart(fig, use_container_width=True)


#cd C:\Users\Ana\pyProj
#python -m streamlit run app.py