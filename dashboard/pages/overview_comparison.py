import polars as pl
import streamlit as st
import plotly.express as px

from data_extract.data_storage import DataStorage
from data_extract.config_manager import ConfigManager

from utils.calculations_helper import (
    calculate_avg_tracks, calculate_avg_popularity, calculate_avg_time,
    prepare_weekday_metrics, prepare_hourly_metrics, plot_metrics
)
from utils.helper import (
    country_to_flag, nationality_to_flag
)

ds = DataStorage()
cm = ConfigManager()
app_config = cm.load_json(path='dashboard/app_config.json')

@st.cache_data
def load_data(path, schema = None):
    data = ds.read_csv(path, schema)
    return data


# Load the data
df_radio_data = load_data(cm.RADIO_CSV_PATH, cm.RADIO_SCRAPPER_SCHEMA)
df_artist_info = load_data(cm.ARTIST_INFO_CSV_PATH, cm.ARTIST_INFO_SCHEMA)
df_track_info = load_data(cm.TRACK_INFO_CSV_PATH, cm.TRACK_INFO_SCHEMA)

df_joined = df_radio_data.join(
        df_artist_info, 
        on=cm.ARTIST_NAME_COLUMN,
        how='left',
    ).join(
        df_track_info,
        on=[cm.TRACK_TITLE_COLUMN, cm.ARTIST_NAME_COLUMN],
        how='left',
    )

# Filter df for data validation checks
# from datetime import datetime
# df_joined = df_joined.filter(
#     pl.col('day') >= datetime(2024, 12, 14),
#     pl.col('day') <= datetime(2024, 12, 20),
# )

# st.write(df)

# Calculate global min and max values
metrics = ['avg_tracks', 'avg_time_played', 'avg_popularity']
metric_ranges = {}

# Initialize config for each radio
for i, (key, val) in enumerate(app_config.items()):
    app_config[key]['radio_df'] = df_joined.filter(
            pl.col(cm.RADIO_COLUMN) == val.get('name')
        )
    for metric in metrics:
        weekday_metric_df = prepare_weekday_metrics(app_config[key]['radio_df'], metric=metric)
        hour_metric_df = prepare_hourly_metrics(app_config[key]['radio_df'], metric=metric)
        if metric not in metric_ranges:
            metric_ranges[metric] = {
                'weekday': {'min': float('inf'), 'max': float('-inf')},
                'hour': {'min': float('inf'), 'max': float('-inf')},
            }
        # Update weekday min/max
        metric_ranges[metric]['weekday']['min'] = min(metric_ranges[metric]['weekday']['min'], weekday_metric_df[metric].min())
        metric_ranges[metric]['weekday']['max'] = max(metric_ranges[metric]['weekday']['max'], weekday_metric_df[metric].max())
        # Update hour min/max
        metric_ranges[metric]['hour']['min'] = min(metric_ranges[metric]['hour']['min'], hour_metric_df[metric].min())
        metric_ranges[metric]['hour']['max'] = max(metric_ranges[metric]['hour']['max'], hour_metric_df[metric].max())

# st.write(metric_ranges)

# Sidebar Settings
with st.sidebar:
    st.title(':gear: Page Settings')
    graph_otion = st.radio(
        'Select Graph to Display:',
        ['Avg Tracks', 'Avg Hours Played', 'Avg Popularity'],
        index=0
    )

graph_metric_map = {
    'Avg Tracks': 'avg_tracks',
    'Avg Hours Played': 'avg_time_played',
    'Avg Popularity': 'avg_popularity'
}
selected_metric = graph_metric_map[graph_otion]

### Header KPIs + Logo
ncols = len(app_config)
header_cols = st.columns(ncols)

for i, (key, val) in enumerate(app_config.items()):
    with header_cols[i]:
        radio_name = val.get('name')
        logo = val.get('logo')
        radio_df = val.get('radio_df')
        # st.image(logo, use_container_width=True)
        with st.container(border=True):
            kpi_1, kpi_2, kpi_3 = st.columns(3)
            kpi_1.metric(
                label='# Avg Tracks per Day',
                value=calculate_avg_tracks(df=radio_df)
            )
            kpi_2.metric(
                label='Avg Hours Played',
                value=calculate_avg_time(df=radio_df, output_unit='hours')
            )
            kpi_3.metric(
                label='Avg Popularity',
                value=calculate_avg_popularity(df=radio_df)
            )


# Time Series Plots Expander
expander = st.expander(label=f'Time Series plots - *{graph_otion}*', expanded=True, icon='📈')
with expander:
    ### WeekDay Graphs
    st.subheader(f'{graph_otion} by weekday', divider="gray")
    weekday_graph_cols = st.columns(ncols)

    for i, (key, val) in enumerate(app_config.items()):
        with weekday_graph_cols[i]:
            radio_name = val.get('name')
            radio_df = val.get('radio_df')
            # Prepare the selected Weekday Metric
            weekday_df = prepare_weekday_metrics(radio_df, metric=selected_metric)
            # st.subheader(f'{graph_otion}')
            plot_metrics(
                weekday_df,
                metric=selected_metric,
                radio_name=radio_name,
                x_axis_column='weekday_name',
                x_axis_label='Day of Week',
                y_axis_range=(
                    metric_ranges[selected_metric]['weekday']['min'] * 0.95,
                    metric_ranges[selected_metric]['weekday']['max'] * 1.05
                ),
                title=''
            )

    ### Hourly Graphs
    st.subheader(f'{graph_otion} by hour', divider="gray")
    hour_graph_cols = st.columns(ncols)

    for i, (key, val) in enumerate(app_config.items()):
        with hour_graph_cols[i]:
            radio_name = val.get('name')
            radio_df = val.get('radio_df')
            hourly_df = prepare_hourly_metrics(radio_df, metric=selected_metric)
            plot_metrics(
                hourly_df,
                metric=selected_metric,
                radio_name=radio_name,
                x_axis_column='hour',
                x_axis_label='Hour of Day',
                y_axis_range=(
                    metric_ranges[selected_metric]['hour']['min'] * 0.95,
                    metric_ranges[selected_metric]['hour']['max'] * 1.05
                ),
                title=''
            )

### Song Statistics
st.header(f':musical_note: Song Statistics', divider="gray")
track_kpis_cols = st.columns(ncols)

for i, (key, val) in enumerate(app_config.items()):
    with track_kpis_cols[i]:
        radio_name = val.get('name')
        radio_df = val.get('radio_df')

        total_tracks = radio_df.height
   
        # Track KPIs
        track_kpi_total, track_kpi_percent = st.columns(2, border=True)
        with track_kpi_total:
            st.metric(
                label='Total Tracks',
                value=total_tracks
            )
            unique_tracks = radio_df.select([pl.col(cm.TRACK_TITLE_COLUMN), pl.col(cm.ARTIST_NAME_COLUMN)]).unique().height
            # st.write(f'{unique_tracks} unique tracks')
            # st.metric(
            #     label='Unique Tracks',
            #     value=unique_tracks
            # )
        percent_unique_tracks = f'{(unique_tracks / total_tracks * 100):.2f}%' if total_tracks > 0 else "N/A"
        with track_kpi_percent:
            st.metric(
                label='% Unique Tracks',
                value=percent_unique_tracks
            )
        
        avg_plays_per_track = f'{(total_tracks / unique_tracks if unique_tracks > 0 else 0):.2f}'
        st.write(f'That means each track is played **{avg_plays_per_track}** times on average')


# Track Plots Expander
track_plots_expander = st.expander(label=f'Song Plots', expanded=True, icon='📊')
with track_plots_expander:
    ### Song Language Statistics
    st.subheader(f':earth_africa: Top 5 Languages by Unique Tracks', divider=False)
    track_plots_cols = st.columns(ncols)

    for i, (key, val) in enumerate(app_config.items()):
        with track_plots_cols[i]:
            radio_name = val.get('name')
            radio_df = val.get('radio_df')

            unique_tracks_by_language = (
                radio_df
                .select([pl.col(cm.TRACK_TITLE_COLUMN), pl.col(cm.ARTIST_NAME_COLUMN), pl.col('lyrics_language')])
                .unique()
                .group_by('lyrics_language')
                .count()
                .sort(by='count', descending=False)
                .tail(5)
            )
            unique_tracks_by_language = unique_tracks_by_language.with_columns(
                (pl.col('count') / unique_tracks_by_language['count'].sum() * 100).alias('percentage')
            )

            unique_tracks_df = unique_tracks_by_language.to_pandas()
            # Map the flags in Pandas instead of Polars
            unique_tracks_df['flag'] = unique_tracks_df['lyrics_language'].map(country_to_flag)

            # Plot top 5 languages for unique tracks
            # st.subheader('Top 5 Languages by Unique Tracks')
            fig = px.bar(
                unique_tracks_df,
                x="count",
                # y=unique_tracks_by_language['lyrics_language'].map_elements(country_to_flag),
                y='flag',
                text="percentage",
                title="",
                orientation='h',
                # labels={"count": "Unique Tracks", "lyrics_language": "Language"}
            )
            # Apply conditional coloring for "Portugal" or "PT"
            colors = [
                "#1f77b4" if lang != "pt" else "#ff7f0e"  # Default color vs highlight color
                for lang in unique_tracks_df["lyrics_language"]
            ]
            fig.update_traces(
                marker_color=colors, # Apply colors manually
                texttemplate="%{text:.1f}%", 
                textposition="outside",
                cliponaxis=False  # Prevent labels from being clipped
            )
            fig.update_layout(
                xaxis_title=None,  # Remove x-axis label
                yaxis_title=None,  # Remove y-axis label
                margin=dict(l=10, r=30, t=30, b=0),  # Add padding around the plot
                # showlegend=False,  # Hide legend if applicable
                # title=dict(x=0.5)  # Center the title
            )
            st.plotly_chart(fig, use_container_width=True, key=f'{radio_name}_unique_tracks_by_language')

    st.divider()

    ### Song Language Statistics
    st.subheader(f':date: Unique Tracks by *decade*', divider=False)
    track_decade_cols = st.columns(ncols)

    for i, (key, val) in enumerate(app_config.items()):
        with track_decade_cols[i]:
            radio_name = val.get('name')
            radio_df = val.get('radio_df')
            # Ensure spotify_release_date is parsed as a date in Polars
            df_tracks_with_date = radio_df.filter(~pl.col("spotify_release_date").is_null())

            # Extract decades for tracks
            df_decades_tracks = (
                df_tracks_with_date
                .with_columns([
                    (pl.col("spotify_release_date").dt.year() // 10 * 10).alias("decade_year"),  # Full year of the decade
                    ((pl.col("spotify_release_date").dt.year() % 100) // 10 * 10).alias("decade_label"),  # Label for the graph (e.g., 80, 90)
                ])
                .select([
                    pl.col("decade_year"),
                    pl.col("decade_label"),
                    pl.col("track_title"),
                    pl.col("artist_name"),
                ])
                .unique()
                .group_by(["decade_year", "decade_label"])
                .count()
                .sort("decade_year")
            )

            # Plot unique tracks by decade
            df_tracks_decade_pandas = df_decades_tracks.to_pandas()
            # st.write(df_tracks_decade_pandas)
            fig_tracks = px.bar(
                df_tracks_decade_pandas,
                x="decade_label",
                y="count",
                title="",
                labels={"decade_label": "Decade", "count": "Unique Tracks"},
                orientation='v',
                text="count",  # Display the count on the bars
            )
            fig_tracks.update_layout(
                xaxis_title=None,
                yaxis_title=None,
                margin=dict(l=10, r=30, t=30, b=0),
                xaxis=dict(type='category', categoryorder='array', categoryarray=df_tracks_decade_pandas["decade_label"].tolist()),  # Ensure proper ordering
            )
            st.plotly_chart(fig_tracks, use_container_width=True, key=f'{radio_name}_unique_tracks_by_decade')

            unique_2024_tracks = radio_df.filter(pl.col('spotify_release_date').dt.year() == 2024).select([pl.col(cm.TRACK_TITLE_COLUMN), pl.col(cm.ARTIST_NAME_COLUMN)]).unique().height
            total_2024_tracks = radio_df.filter(pl.col('spotify_release_date').dt.year() == 2024).height
            st.markdown(
                f'''**{unique_2024_tracks}** unique tracks released in :blue[2024], and were played a total of **{total_2024_tracks}** times
                \ni.e. **{(total_2024_tracks / unique_2024_tracks):.1f}** times per track'''
            )
            # st.write(f'i.e. {(total_2024_tracks / unique_2024_tracks):.1f} times per track')


### Artist Statistics
st.header(f':microphone: Artist Statistics', divider="gray")
artist_kpis_cols = st.columns(ncols)

for i, (key, val) in enumerate(app_config.items()):
    with artist_kpis_cols[i]:
        radio_name = val.get('name')
        radio_df = val.get('radio_df')
        total_tracks = radio_df.height

         # Artists KPIs
        artist_kpi_total, artist_kpi_percent = st.columns(2, border=True)
        with artist_kpi_total:
            unique_artists = radio_df.select(pl.col(cm.ARTIST_NAME_COLUMN)).unique().height
            st.metric(
                label='Unique Artists',
                value=unique_artists
            )
            
        with artist_kpi_percent:
            percent_unique_artists = f'{(unique_artists / total_tracks * 100):.2f}%' if total_tracks > 0 else "N/A"
            avg_plays_per_artist = f'{(total_tracks / unique_artists if unique_artists > 0 else 0):.2f}'
            st.metric(
                label='Avg Songs per Artist',
                value=avg_plays_per_artist
            )

# Artist Plots Expander
artist_plots_expander = st.expander(label=f'Artists Plots', expanded=True, icon='📊')
with artist_plots_expander:
    ### Artists Country Statistics
    st.header(f':earth_africa: Artists Statistics', divider="gray")
    artist_plots_cols = st.columns(ncols)

    for i, (key, val) in enumerate(app_config.items()):
        with artist_plots_cols[i]:
            radio_name = val.get('name')
            radio_df = val.get('radio_df')
            unique_artists_by_country = (
                radio_df
                .select([pl.col(cm.ARTIST_NAME_COLUMN), pl.col('combined_nationality')])
                .unique()
                .group_by('combined_nationality')
                .count()
                .sort(by='count', descending=False)
                .tail(5)
            )
            unique_artists_by_country = unique_artists_by_country.with_columns(
                (pl.col('count') / unique_artists_by_country['count'].sum() * 100).alias('percentage')
            )

            unique_artists_df = unique_artists_by_country.to_pandas()
            unique_artists_df['flag'] = unique_artists_df['combined_nationality'].map(nationality_to_flag)

            # Plot top 5 countries for unique artists
            fig = px.bar(
                unique_artists_df,
                x="count",
                y='flag',
                text="percentage",
                title="",
                orientation='h',
            )
            # Apply conditional coloring for "Portugal" or "PT"
            colors = [
                "#1f77b4" if country != "Portugal" else "#ff7f0e"  # Default color vs highlight color
                for country in unique_artists_df["combined_nationality"]
            ]
            fig.update_traces(
                marker_color=colors,
                texttemplate="%{text:.1f}%", 
                textposition="outside",
                cliponaxis=False  # Prevent labels from being clipped
            )
            fig.update_layout(
                xaxis_title=None,  # Remove x-axis label
                yaxis_title=None,  # Remove y-axis label
                margin=dict(l=10, r=30, t=30, b=0),  # Add padding around the plot
            )
            st.plotly_chart(fig, use_container_width=True, key=f'{radio_name}_unique_artists_by_country')
    
    ### Artists Country Statistics
    st.header(f':date: Unique Artists by *decade*', divider="gray")
    artist_decade_cols = st.columns(ncols)

    for i, (key, val) in enumerate(app_config.items()):
        with artist_decade_cols[i]:
            radio_name = val.get('name')
            radio_df = val.get('radio_df')
            # Ensure spotify_release_date is parsed as a date in Polars
            df_artists_with_date = radio_df.filter(~pl.col("mb_artist_career_begin").is_null())

            # Extract decades for tracks
            df_decades_artists = (
                df_artists_with_date
                .with_columns([
                    (pl.col("mb_artist_career_begin").dt.year() // 10 * 10).alias("decade_year"),  # Full year of the decade
                    ((pl.col("mb_artist_career_begin").dt.year() % 100) // 10 * 10).alias("decade_label"),  # Label for the graph (e.g., 80, 90)
                ])
                .select([
                    pl.col("decade_year"),
                    pl.col("decade_label"),
                    pl.col("artist_name"),
                ])
                .unique()
                .group_by(["decade_year", "decade_label"])
                .count()
                .sort("decade_year")
            )

            # Plot unique tracks by decade
            df_artists_decade_pandas = df_decades_artists.to_pandas()
            # st.write(df_artists_decade_pandas)
            fig_tracks = px.bar(
                df_artists_decade_pandas,
                x="decade_year",
                y="count",
                title="",
                labels={"decade_year": "Decade", "count": "Unique Artists"},
                orientation='v',
                text="count",  # Display the count on the bars
            )
            fig_tracks.update_layout(
                xaxis_title=None,
                yaxis_title=None,
                margin=dict(l=10, r=30, t=30, b=0),
                xaxis=dict(type='category', categoryorder='array', categoryarray=df_artists_decade_pandas["decade_year"].tolist()),  # Ensure proper ordering
            )
            st.plotly_chart(fig_tracks, use_container_width=True, key=f'{radio_name}_unique_artists_by_decade')



### Song Duration
st.subheader(f':clock4: Song Duration (minutes)', divider="gray")
track_duration_cols = st.columns(ncols)

for i, (key, val) in enumerate(app_config.items()):
    with track_duration_cols[i]:
        radio_name = val.get('name')
        radio_df = val.get('radio_df')

        # Ensure spotify_duration_ms is not null
        df_tracks_with_duration = radio_df.filter(~pl.col("spotify_duration_ms").is_null())

        # Convert duration to minutes (truncated)
        df_duration_tracks = (
            df_tracks_with_duration
            .with_columns([
                (pl.col("spotify_duration_ms") / 60000).floor().cast(int).alias("duration_minutes")  # Convert to minutes and truncate
            ])
            .select([
                pl.col("duration_minutes"),
                pl.col("track_title"),
                pl.col("artist_name"),
            ])
            .unique()
            .group_by("duration_minutes")
            .count()
            .sort("duration_minutes")
        )

        # Convert to Pandas for Plotly
        df_duration_pandas = df_duration_tracks.to_pandas()

        # Calculate Percentage
        total_tracks = df_duration_pandas["count"].sum()
        df_duration_pandas["percentage"] = (df_duration_pandas["count"] / total_tracks) * 100

        # Create a label column with "number (percentage)"
        df_duration_pandas["label"] = df_duration_pandas.apply(
            lambda row: f"{row['count']:.0f} ({row['percentage']:.1f}%)", axis=1
        )

        # Plot unique tracks by truncated duration
        fig_duration = px.bar(
            df_duration_pandas,
            x="duration_minutes",
            y="count",
            title="",
            labels={"duration_minutes": "Track Duration (Minutes)", "count": "Number of Unique Tracks"},
            orientation='v',
            text="label",  # Use the custom label
        )
        fig_duration.update_traces(
            marker_color="#d3d3d3",  # Light gray for bars
            texttemplate="%{text}", 
            textposition="outside"
        )
        fig_duration.update_layout(
            xaxis_title=None,
            yaxis_title=None,
            margin=dict(l=10, r=30, t=30, b=0),
            xaxis=dict(type='category'),  # Ensure durations are treated as categories
            yaxis=dict(title="Number of Unique Tracks", tickformat=",")
        )
        st.plotly_chart(fig_duration, use_container_width=True, key=f"{radio_name}_unique_tracks_by_duration")


### Genres
st.subheader(f':musical_score: Top 10 Genres', divider="gray")
genre_cols = st.columns(ncols)

for i, (key, val) in enumerate(app_config.items()):
    with genre_cols[i]:
        radio_name = val.get('name')
        radio_df = val.get('radio_df')
        # Extract and group genres
        # Ensure spotify_genres column is not null
        df_genres_cleaned = (
            radio_df
            .filter(
                (~pl.col("spotify_genres").is_null())
                & (pl.col("spotify_genres") != ""),
            )
            .with_columns([
                pl.col("spotify_genres").str.split(", ").alias("split_genres")  # Split comma-separated genres into lists
            ])
            .explode("split_genres")  # Explode the lists into rows
            .group_by("split_genres")
            .count()
            .sort("count", descending=False)
            .tail(10)  # Show top 10 genres
        )

        # Convert to Pandas for Plotly
        df_genres_pandas = df_genres_cleaned.rename({"split_genres": "spotify_genres"}).to_pandas()

        # Plot horizontal bar chart
        fig_genres = px.bar(
            df_genres_pandas,
            x="count",
            y="spotify_genres",
            title="",
            labels={"count": "Track Count", "spotify_genres": "Genre"},
            orientation="h",
            text="count",  # Show count on bars
        )
        fig_genres.update_traces(
            texttemplate="%{text}", 
            textposition="outside",
            cliponaxis=False  # Prevent labels from being clipped
        )
        fig_genres.update_layout(
            xaxis_title=None,
            yaxis_title=None,
            margin=dict(l=150, r=30, t=30, b=10),  # Adjust for long genre names
        )
        st.plotly_chart(fig_genres, use_container_width=True, key=f"{radio_name}_top_genres")


        st.write(radio_df)
        

# Perhaps make Avg Hours as the first/main graph
# Create logos for radios of the same size
# Use only 1 title for each section, instead of having it repeat for every column
# Improve visual by trying to add some borders or background colors
# Color PT bar differently
# Don't have 2 columns for track/artist but instead 1 column with artists following tracks. With dividers
# Allow choosing to see metric of number of unique tracks or number of total tracks
# For graph by Track Duration allow to see by number of total tracks or by percentage
# Reduce file size with helper functions, if possible

# Consider using tabs for Songs/Artists statistics
# Format Total Tracks with separator
# Add a button to choose between 'Total Tracks' or 'Unique Tracks'
# Improve graph tooltips
# Improve texts with markdown format