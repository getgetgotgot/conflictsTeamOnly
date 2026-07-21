import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
st.set_page_config(layout="wide")

# Load data
gdelt_df = pd.read_csv("https://raw.githubusercontent.com/getgetgotgot/conflictsTeamOnly/main/gdelt_result_1.csv")
news_df = pd.read_csv("https://raw.githubusercontent.com/getgetgotgot/conflictsTeamOnly/main/dataforseo_result_1.csv")

gdelt_df_2 = pd.read_csv("https://raw.githubusercontent.com/getgetgotgot/conflictsTeamOnly/main/gdelt_result_2.csv")
news_df_2 = pd.read_csv("https://raw.githubusercontent.com/getgetgotgot/conflictsTeamOnly/main/dataforseo_result_2_2.csv")

st.title("GDELT vs DataForSEO")

tab1, tab2, tab3 = st.tabs(
    ["Test 1", "Test 2", "Test 3 (Coming soon)"]
)

# ---------------------------
# Relevance summary helper
# ---------------------------

def relevance_counts(series):
    s = (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return {
        "Yes": (s == "yes").sum(),
        "No": (s == "no").sum(),
        "Partial No": s.isin(["no*", "no**"]).sum(),
    }
def plot_relevance_bar(counts):
    total = sum(counts.values())

    if total == 0:
        st.write("No annotated articles.")
        return

    yes = counts["Yes"] / total * 100
    partial = counts["Partial No"] / total * 100
    no = counts["No"] / total * 100

    fig, ax = plt.subplots(figsize=(5, 0.45))

    ax.barh([""], yes, label="Yes")
    ax.barh([""], partial, left=yes, label="No*/No**")
    ax.barh([""], no, left=yes + partial, label="No")

    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("% of articles", fontsize=8)
    ax.set_yticks([])


    st.pyplot(fig, use_container_width=True)
    plt.close(fig)
with tab1:

    st.write("""
    ### Approach

    - Used GDELT to estimate baseline media visibility for each conflict:
      - Random sample of 100 events from the UCDP GED dataset
      - Retrieved article counts for the sample
      - Created a LOW tier containing 0-article events
      - Split remaining events into MEDIUM and HIGH tiers based on the median
      - Randomly selected one representative event from each tier

    - Queried Google News through DataForSEO using:
      - The selected event
      - The event date window
      - English plus available local language/location combinations
      - Query translation using a free translation API

    - Manually reviewed:
      - All retrieved results (or the first 10 if more than 10)
      - Whether each article relates to:
        - the conflict in the selected area
        - the specific UCDP event
    """)

    # ---------------------------
    # Conflict selector
    # ---------------------------

    conflicts = sorted(gdelt_df["location"].dropna().unique())

    selected_location = st.selectbox(
        "Select conflict",
        conflicts
    )

    # Filter both datasets
    gdelt = gdelt_df[gdelt_df["location"] == selected_location]
    news = news_df[news_df["location"] == selected_location]
    
    # GDELT summaries
    gdelt_conflict = relevance_counts(gdelt["related_to_conflict_in_area"])
    gdelt_event = relevance_counts(gdelt["related_to_specific_event"])
    

# DataForSEO summaries
    news_conflict = relevance_counts(news["relevant_to_conflict_in_area"])
    news_event = relevance_counts(news["relevant_to_specific_event"])

    # Metadata
    tier = gdelt["tier"].iloc[0]
    country = gdelt["country"].iloc[0]

    st.subheader(f"{selected_location}, {country}")
    st.write(f"**Tier:** {tier}")

    # Metrics
    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "GDELT articles",
            gdelt["total_article_count"].iloc[0]
        )

    with c2:
        st.metric(
            "DataForSEO results",
            news["d4s_article_count"].iloc[0]
        )

    st.divider()

        # ---------------------------
    # Side-by-side tables
    # ---------------------------

    left, right = st.columns(2)

    with left:
        
        st.subheader("GDELT")

        st.markdown("##### Related to conflict in area")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", gdelt_conflict["Yes"])
        c2.metric("No", gdelt_conflict["No"])
        c3.metric("No*/No**", gdelt_conflict["Partial No"])
        plot_relevance_bar(gdelt_conflict)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")

        st.markdown("##### Related to specific event")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", gdelt_event["Yes"])
        c2.metric("No", gdelt_event["No"])
        c3.metric("No*/No**", gdelt_event["Partial No"])
        plot_relevance_bar(gdelt_event)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")

        st.dataframe(
            gdelt[
                [
                    "url",
                    "related_to_conflict_in_area",
                    "related_to_specific_event",
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    with right:

        st.subheader("DataForSEO")

        st.markdown("##### Related to conflict in area")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", news_conflict["Yes"])
        c2.metric("No", news_conflict["No"])
        c3.metric("No*/No**", news_conflict["Partial No"])
        plot_relevance_bar(news_conflict)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")
        st.markdown("##### Related to specific event")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", news_event["Yes"])
        c2.metric("No", news_event["No"])
        c3.metric("No*/No**", news_event["Partial No"])
        plot_relevance_bar(news_event)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")

        st.dataframe(
            news[
                [
                    "rank_absolute",
                    "title",
                    "domain",
                    "query_language",
                    "relevant_to_conflict_in_area",
                    "relevant_to_specific_event",
                    "url",
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.info("""
    **Annotation notes**

    - **No*** = article relates to military tensions but not the conflict directly (e.g. acquisition of military equipment).
    - **No**** = article broadly relates to the conflict but not to the specific UCDP event (e.g. reports of drone strikes in the area without referring to the queried event).
    """)
    st.write("""
    ### Findings

    - DataforSEO shows slightly more consistent relevance (Test 1 + Test 2)
    - Difficult to draw conclusion on which has more article; this varies by location
    - Based on Test 1 and 2 and previous attempts, very low visibility conflicts seem to not be covered by either 
    - Test 1 and Test 2 returned no results in other languages in DataforSEO, while GDELT returned some (across manually screened samples)
    - It is difficult to obtain news articles related to one particular event on one particular date. Many events happen in areas where conflict is prevalent over a longer span of time, meaning that news cover events broadly.
    - Would it be a possible solution to aggregate per location and use the date of the first logged event as the starting date, with the date of the last logged event + buffer as the end date of the query?
    
    """)

with tab2:

    st.write("""
    ### Approach

    - Used GDELT to estimate baseline media visibility for each conflict:
      - Random sample of 100 events from the UCDP GED dataset
      - Retrieved article counts for the sample
      - Created a LOW tier containing 0-article events
      - Split remaining events into MEDIUM and HIGH tiers based on the median
      - Randomly selected one representative event from each tier

    - Queried Google News through DataForSEO using:
      - The selected event
      - The event date window
      - English plus available local language/location combinations
      - Query translation using a free translation API

    - Manually reviewed:
      - All retrieved results (or the first 10 if more than 10)
      - Whether each article relates to:
        - the conflict in the selected area
        - the specific UCDP event
    """)

    # ---------------------------
    # Conflict selector
    # ---------------------------

    conflicts_2 = sorted(gdelt_df_2["location"].dropna().unique())

    selected_location_2 = st.selectbox(
        "Select conflict",
        conflicts_2,
        key="tab2_conflict_select"
    )

    # Filter both datasets
    gdelt2 = gdelt_df_2[gdelt_df_2["location"] == selected_location_2]
    news2 = news_df_2[news_df_2["location"] == selected_location_2]
    
    # GDELT summaries
    gdelt_conflict2 = relevance_counts(gdelt2["related_to_conflict_in_area"])
    gdelt_event2 = relevance_counts(gdelt2["related_to_specific_event"])
    

# DataForSEO summaries
    news_conflict2 = relevance_counts(news2["relevant_to_conflict_in_area"])
    news_event2 = relevance_counts(news2["relevant_to_specific_event"])

    # Metadata
    tier2 = gdelt2["tier"].iloc[0]
    country2 = gdelt2["country"].iloc[0]

    st.subheader(f"{selected_location_2}, {country2}")
    st.write(f"**Tier:** {tier2}")

    # Metrics
    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "GDELT articles",
            gdelt2["total_article_count"].iloc[0]
        )

    with c2:
        st.metric(
            "DataForSEO results",
            news2["d4s_article_count"].iloc[0]
        )

    st.divider()

        # ---------------------------
    # Side-by-side tables
    # ---------------------------

    left, right = st.columns(2)

    with left:
        
        st.subheader("GDELT")

        st.markdown("##### Related to conflict in area")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", gdelt_conflict2["Yes"])
        c2.metric("No", gdelt_conflict2["No"])
        c3.metric("No*/No**", gdelt_conflict2["Partial No"])
        plot_relevance_bar(gdelt_conflict2)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")

        st.markdown("##### Related to specific event")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", gdelt_event2["Yes"])
        c2.metric("No", gdelt_event2["No"])
        c3.metric("No*/No**", gdelt_event2["Partial No"])
        plot_relevance_bar(gdelt_event2)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")

        st.dataframe(
            gdelt2[
                [
                    "url",
                    "related_to_conflict_in_area",
                    "related_to_specific_event",
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    with right:

        st.subheader("DataForSEO")

        st.markdown("##### Related to conflict in area")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", news_conflict2["Yes"])
        c2.metric("No", news_conflict2["No"])
        c3.metric("No*/No**", news_conflict2["Partial No"])
        plot_relevance_bar(news_conflict2)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")
        st.markdown("##### Related to specific event")
        c1, c2, c3 = st.columns(3)
        c1.metric("Yes", news_event2["Yes"])
        c2.metric("No", news_event2["No"])
        c3.metric("No*/No**", news_event2["Partial No"])
        plot_relevance_bar(news_event2)
        st.caption("🟦 Yes   🟧 No*/No**   🟩 No")

        st.dataframe(
            news2[
                [
                    "rank_absolute",
                    "title",
                    "domain",
                    "query_language",
                    "relevant_to_conflict_in_area",
                    "relevant_to_specific_event",
                    "url",
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.info("""
    **Annotation notes**

    - **No*** = article relates to military tensions but not the conflict directly (e.g. acquisition of military equipment).
    - **No**** = article broadly relates to the conflict but not to the specific UCDP event (e.g. reports of drone strikes in the area without referring to the queried event).
    """)