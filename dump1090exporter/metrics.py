'''
This module defines the metrics that will be exposed to Prometheus.

The metrics are grouped under two top level keys which represent the two data
files that the data is extracted from. Aircraft metrics are extracted from the
data/aircraft.json file. Statistics metrics are extracted from the
data/stats.json file.

Each metric specification item consists of a 3-tuple. The first element
represents a name used within the application to uniquely reference the metric
object. The next two elements represent the Prometheus metric label and its
help string.

When the application creates the actual Prometheus metrics labels it prefixes
`dump1090_` onto each label to namespace the metrics under a common name. In
the case of the stats group of metrics it also adds a `stats_` to the prefix
to group the stats with a common label prefix.

So an item listed under the aircraft section, for example the 'messages_total'
item, will end up with a Prometheus metric label of:

.. code-block:: console

    dump1090_messages_total

An item listed under the stats section, for example the 'stats_messages_total'
item, will end up with a Prometheus metric label of:

.. code-block:: console

    dump1090_stats_messages_total

There are multiple sections in the dump1090 stats data file. The Prometheus
multi-dimensional metrics label are used to expose these. So to obtain the
stats metrics for the last1min group you would use a metrics label of:

.. code-block:: console

    dump1090_stats_messages_total{job="dump1090", time_period="last1min"}

To extract the totals since the dump1090 application started:

.. code-block:: console

    dump1090_stats_messages_total{job="dump1090", time_period="total"}

'''

Specs = {
    'aircraft': (
        ('observed', 'recent_aircraft_observed', 'Number of aircraft recently observed'),
        ('observed_with_pos', 'recent_aircraft_with_position', 'Number of aircraft recently observed with position'),
        ('observed_with_mlat', 'recent_aircraft_with_multilateration', 'Number of aircraft recently observed with multilateration'),
        ('max_range', 'aircraft_recent_max_range', 'Maximum range of recently observed aircraft'),
        ('messages_total', 'messages_total', 'Number of Mode-S messages processed since start up')
    ),
    'stats': {
        # top level items not in a sub-group are listed under this empty key.
        '': (
            ('messages', 'stats_messages_total', 'Number of Mode-S messages processed'),
        ),
        'cpr': (
            ('airborne', 'stats_cpr_airborne', 'Number of airborne CPR messages received'),
            ('surface', 'stats_cpr_surface', 'Number of surface CPR messages received'),
            ('filtered', 'stats_cpr_filtered', 'Number of CPR messages ignored'),
            ('global_bad', 'stats_cpr_global_bad', 'Global positions that were rejected'),
            ('global_ok', 'stats_cpr_global_ok', 'Global positions successfuly derived'),
            ('global_range', 'stats_cpr_global_range', 'Global positions rejected due to receiver max range check'),
            ('global_skipped', 'stats_cpr_global_skipped', 'Global position attempts skipped due to missing data'),
            ('global_speed', 'stats_cpr_global_speed', 'Global positions rejected due to speed check'),
            ('local_aircraft_relative', 'stats_cpr_local_aircraft_relative', 'Local positions found relative to a previous aircraft position'),
            ('local_ok', 'stats_cpr_local_ok', 'Local (relative) positions successfully found'),
            ('local_range', 'stats_cpr_local_range', 'Local positions rejected due to receiver max range check'),
            ('local_receiver_relative', 'stats_cpr_local_receiver_relative', 'Local positions found relative to the receiver position'),
            ('local_skipped', 'stats_cpr_local_skipped', 'Local (relative) positions skipped due to missing data'),
            ('local_speed', 'stats_cpr_local_speed', 'Local positions rejected due to speed check'),
        ),
        'cpu': (
            ('background', 'stats_cpu_background_milliseconds', 'Time spent in network I/O, processing and periodic tasks'),
            ('demod', 'stats_cpu_demod_milliseconds', 'Time spent demodulation and decoding data from SDR dongle'),
            ('reader', 'stats_cpu_reader_milliseconds', 'Time spent reading sample data from SDR dongle'),
        ),
        'local': (
            ('accepted', 'stats_local_accepted', 'Number of valid Mode S messages accepted with N-bit errors corrected'),
            ('signal', 'stats_local_signal_strength_dbFS', 'Signal strength dbFS'),
            ('peak_signal', 'stats_local_peak_signal_strength_dbFS', 'Peak signal strength dbFS'),
            ('noise', 'stats_local_noise_level_dbFS', 'Noise level dbFS'),
            ('strong_signals', 'stats_local_strong_signals', 'Number of messages that had a signal power above -3dBFS'),
            ('bad', 'stats_local_bad',"Number of Mode S preambles that didn't result in a valid message"),
            ('modes', 'stats_local_modes', 'Number of Mode S preambles received'),
            ('modeac', 'stats_local_modeac', 'Number of Mode A/C preambles decoded'),
            ('samples_dropped', 'stats_local_samples_dropped','Number of samples dropped'),
            ('samples_processed', 'stats_local_samples_processed', 'Number of samples processed'),
            ('unknown_icao', 'stats_local_unknown_icao', 'Number of Mode S preambles containing unrecognized ICAO'),
        ),
        'remote': (
            ('accepted', 'stats_remote_accepted', 'Number of valid Mode S messages accepted with N-bit errors corrected'),
            ('bad', 'stats_remote_bad', "Number of Mode S preambles that didn't result in a valid message"),
            ('modeac', 'stats_remote_modeac', 'Number of Mode A/C preambles decoded'),
            ('modes', 'stats_remote_modes', 'Number of Mode S preambles received'),
            ('unknown_icao', 'stats_remote_unknown_icao', 'Number of Mode S preambles containing unrecognized ICAO'),
        ),
        'tracks': (
            ('all', 'stats_tracks_all', 'Number of tracks created'),
            ('single_message', 'stats_tracks_single_message', 'Number of tracks consisting of only a single message'),
        ),
    }
}
