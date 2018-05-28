"""
Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You may be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -mjanggu` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``janggu.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``janggu.__main__`` in ``sys.modules``.

  Also see (1) from http://click.pocoo.org/5/setuptools/#setuptools-integration
"""

import argparse
import base64
import glob
import os

try:
    import dash  # pylint: disable=import-error
    import dash_core_components as dcc  # pylint: disable=import-error
    import dash_html_components as html  # pylint: disable=import-error
    import plotly.graph_objs as go  # pylint: disable=import-error
except ImportError as ex_:
    print('dash not available. Please install dash, dash_renderer, '
          'dash_core_components'
          ' and dash_html_components to be able to use the janggu app.')
import pandas as pd
from scipy.stats import zscore
try:
    from sklearn.decomposition import PCA  # pylint: disable=import-error
    from sklearn.manifold import TSNE  # pylint: disable=import-error
except ImportError as ex_:
    print('scikit-learn not available. Please install scikit-learn.')
    raise(ex_)

PARSER = argparse.ArgumentParser(description='Command description.')
PARSER.add_argument('-path', dest='janggu_results',
                    default=os.path.join(os.path.expanduser("~"),
                                         'janggu_results'),
                    help="Janggu results path.")

ARGS = PARSER.parse_args()

APP = dash.Dash('Janggu')
APP.title = 'Janggu'
APP.config['suppress_callback_exceptions'] = True

def _serve_layer():
    return html.Div([
        dcc.Location(id='url', refresh=False),
        html.Nav(
            html.Div(
                [html.Div([
                    dcc.Link(html.H2('Janggu'),
                             href='/', className='navbar-brand')],
                          className='navbar-header'),
                 html.Div(
                     html.Ul([html.Li(dcc.Link('Logs', href='/logs')),
                              html.Li(dcc.Link('Model Comparison',
                                               href='/model_comparison'))],
                             className='nav navbar-nav'),
                     className='container-fluid')],
                className='navbar navbar-default navbar-expand-lg navbar-dark')),
        html.Br(),
        html.Div(id='page-content')
    ], className='container')


APP.layout = _serve_layer()


@APP.callback(dash.dependencies.Output('page-content', 'children'),
              [dash.dependencies.Input('url', 'pathname')])
def _display_page(pathname):  # pylint: disable=too-many-return-statements
    if pathname is None:
        return html.Div([])
    elif pathname == '/':
        files = glob.glob(os.path.join(ARGS.janggu_results, 'models', '*.png'))
        if not files:
            return html.Div([
                html.P('The directory "{}" appears to be empty.'
                       .format(ARGS.janggu_results))])
        encoding = {os.path.basename(os.path.splitext(name)[0]):
                    base64.b64encode(open(name, 'rb').read())
                    for name in files}

        return html.Div([
            html.Table(
                [html.Tr([html.Th('Model name'), html.Th('Architecture')])] +
                [html.Tr([dcc.Link(html.Td(name), href='/{}'.format(name)),
                          html.Td(html.Img(
                              id=name, width='50%',
                              src='data:image/png;base64,{}'.format(
                                  encoding[name].decode())))])
                 for name in encoding],
                className='table table-bordered')])
    elif pathname == '/logs':
        return html.Div(
            html.Pre(open(os.path.join(ARGS.janggu_results, 'logs', 'janggu.log')).read())
        )
    elif pathname == '/model_comparison':
        return _model_comparison_page()
    else:
        files = []
        root = os.path.join(ARGS.janggu_results, 'evaluation', pathname[1:])
        pathlen = len(root) + 1
        for root, dirnames, filenames in os.walk(root):
            for filename in filenames:
                if filename.endswith('.png') or \
                        filename.endswith('.tsv') or filename.endswith('.ply'):

                    path = tuple(dirnames) + (filename,)

                    files += [os.path.join(root, *path)]

        if not files:
            return html.Div([html.H3('No figures available for {}'.format(pathname[1:]))])

        return html.Div([html.H3('Model: {}'.format(pathname[1:])),
                         dcc.Dropdown(id='tag-selection',
                                      options=[{'label': f[pathlen:],
                                                'value': f} for f in files],
                                      value=files[0]),
                         html.Div(id='output-plot')])


def _model_comparison_page():
    print('_model_comparison_page')
    combined_tables = {}
    #
    root = os.path.join(ARGS.janggu_results, 'evaluation')

    for root, _, filenames in os.walk(root):

        for filename in filenames:
            if filename.endswith('.tsv'):
                df_ = pd.read_csv(os.path.join(root, filename),
                                  sep='\t', header=[0], nrows=2)
                if df_.shape[0] > 1:
                    continue
                scorename = os.path.splitext(filename)[0]
                if scorename not in combined_tables:
                    combined_tables[scorename] = []
                combined_tables[scorename].append(os.path.join(root, filename))
    first_score = list(combined_tables.keys())[0]
    return html.Div([html.H3('Model Comparison'),
                     dcc.Dropdown(id='score-selection',
                                  options=[{'label': f,
                                            'value': (f, combined_tables[f])}
                                           for f in combined_tables],
                                  value=(first_score,
                                         combined_tables[first_score])),
                     html.Div(id='output-modelcomparison')])


@APP.callback(
    dash.dependencies.Output('output-modelcomparison', 'children'),
    [dash.dependencies.Input('score-selection', 'value')])
def _update_modelcomparison(results):

    if results is None:
        return html.P('No results for model comparison selected or detected.')

    label = results[0]
    results = results[1]
    header = ['Model', 'Layer', 'Condition', label]
    thead = [html.Tr([html.Th(h) for h in header])]
    tbody = []
    allresults = pd.DataFrame([], columns=header)
    print(results)
    for tab in results:
        df_ = pd.read_csv(tab, sep='\t', header=[0])
        names = df_.columns[0].split('-')
        mname, lname, cname = names[0], names[1], '-'.join(names[2:])
        allresults = allresults.append({'Model': mname,
                                        'Layer': lname,
                                        'Condition': cname,
                                        label: df_[df_.columns[0]][0]},
                                       ignore_index=True)
    allresults.sort_values(label, ascending=False, inplace=True)

    tbody = [html.Tr([
        html.Td(allresults.iloc[i][col]) for col in header
    ]) for i in range(len(allresults))]

    return html.Table(thead + tbody)


@APP.callback(
    dash.dependencies.Output('output-plot', 'children'),
    [dash.dependencies.Input('tag-selection', 'value')])
def _update_output(value):

    if value.endswith('png'):
        # display the png images directly
        img = base64.b64encode(open(value, 'rb').read())
        return html.Img(width='100%',
                        src='data:image/png;base64,{}'.format(img.decode()))

    elif value.endswith('tsv'):
        max_rows = 20
        df_ = pd.read_csv(value, sep='\t', header=[0])
        if df_.shape[0] == 1:
            df_ = df_.transpose()
            df_.columns = ['score']
        return html.Table(
            # Header
            [html.Tr([html.Th(col) for col in df_.columns])] +

            # Body
            [html.Tr([
                html.Td(df_.iloc[i][col]) for col in df_.columns
            ]) for i in range(min(len(df_), max_rows))]
        )

    elif value.endswith('ply'):
        dfheader = pd.read_csv(value, sep='\t', header=[0], nrows=0)
        # read the annotation for the dropdown
        annot = []
        for col in dfheader.columns:
            if col[:len('annot.')] == 'annot.':
                annot.append(col[len('annot.'):])

        return html.Div([
            html.Div([
                dcc.Dropdown(id='xaxis',
                             options=[{'label': x,
                                       'value': x}
                                      for x in ['Component {}'.format(i)
                                                for i in [1, 2, 3]]],
                             value='Component 1'),
                dcc.Dropdown(id='yaxis',
                             options=[{'label': x,
                                       'value': x}
                                      for x in ['Component {}'.format(i)
                                                for i in [1, 2, 3]]],
                             value='Component 2'),
                dcc.Graph(id='scatter')],
                     style={'width': '100%',
                            'display': 'inline-block',
                            'padding': '0 20'}),
            html.Div([
                dcc.Dropdown(id='operation',
                             options=[{'label': x,
                                       'value': x}
                                      for x in ['pca', 'tsne']],
                             value='pca'),
                dcc.Dropdown(id='annotation',
                             options=[{'label': x,
                                       'value': x} for x in ['None'] + annot],
                             value='None'),
                dcc.Graph(id='features')],
                     style={'width': '100%',
                            'display': 'inline-block',
                            'padding': '0 20'}),
        ], style={'columnCount': 2})

    # else the value is not known
    return html.P('Cannot find action for {}'.format(value))


@APP.callback(
    dash.dependencies.Output('scatter', 'figure'),
    [dash.dependencies.Input('tag-selection', 'value'),
     dash.dependencies.Input('operation', 'value'),
     dash.dependencies.Input('xaxis', 'value'),
     dash.dependencies.Input('yaxis', 'value'),
     dash.dependencies.Input('annotation', 'value')])
def _update_scatter(filename, operation,  # pylint: disable=too-many-locals
                    xaxis_label,
                    yaxis_label,
                    annotation):
    data = pd.read_csv(filename, sep='\t', header=[0])

    # if 'annot' in data use coloring
    colors = pd.Series(['blue'] * data.shape[0])
    for col in data:
        if col[:len('annot.')] == 'annot.':
            if annotation == col[len('annot.'):]:
                colors = data[col]
            data.pop(col)
        if col == 'row_names':
            text = data.pop(col)

    if operation == 'pca':
        pca = PCA(n_components=3)
        trdata = pca.fit_transform(data)
    else:
        tsne = TSNE(n_components=3)
        trdata = tsne.fit_transform(data)
    trdata = pd.DataFrame(trdata, columns=['Component {}'.format(i)
                                           for i in [1, 2, 3]])

    data = []
    for color in colors.unique():
        data.append(
            go.Scatter(
                x=trdata[xaxis_label][colors == color],
                y=trdata[yaxis_label][colors == color],
                text=text,
                name=color,
                customdata=colors[colors == color].index,
                mode='markers',
                marker=dict(size=3, opacity=.5)))

    return {'data': data,
            'layout': go.Layout(
                margin={'l': 40, 'b': 30, 't': 10, 'r': 0},
                xaxis={'title': xaxis_label},
                yaxis={'title': yaxis_label},
                hovermode='closest',
                plot_bgcolor='#E5E5E5',
                paper_bgcolor='#E5E5E5'
            )
           }


@APP.callback(
    dash.dependencies.Output('features', 'figure'),
    [dash.dependencies.Input('tag-selection', 'value'),
     dash.dependencies.Input('operation', 'value'),
     dash.dependencies.Input('scatter', 'selectedData')])
def _update_features(value, feature, selected):
    data = pd.read_csv(value, sep='\t', header=[0])
    data.reindex(sorted(data.columns), axis=1)

    print('_update_features')

    for col in data:
        if col[:len('annot')] == 'annot':
            data.pop(col)
        if col == 'row_names':
            data.pop(col)

    data = data.apply(zscore)
    if selected is not None:
        selected_idx = [datum['customdata'] for datum in selected['points']]
        data = data.iloc[selected_idx, :]

    mean = data.mean().values
    std = data.std().values

    return {'data': [go.Scatter(
        x=list(range(len(mean))),
        y=mean,
        mode='line',
        text=data.columns,
        error_y=dict(
            type='percent',
            value=std,
            thickness=1,
            width=0,
            color='#444',
            opacity=0.8
        ))],
            'layout': go.Layout(
                xaxis={'title': 'Features'},
                plot_bgcolor='#E5E5E5',
                paper_bgcolor='#E5E5E5',
                yaxis={'showgrid': False,
                       'title': 'Activities (z-score)'}
            )
           }


CSSES = ["https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css",
         "https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/css/bootstrap.min.css",
         "https://codepen.io/chriddyp/pen/bWLwgP.css"]

for css in CSSES:
    APP.css.append_css({"external_url": css})

JSES = ["http://code.jquery.com/jquery-3.3.1.min.js",
        "https://maxcdn.bootstrapcdn.com/bootstrap/4.0.0/js/bootstrap.min.js"]

for js in JSES:
    APP.scripts.append_script({"external_url": js})


def main():
    """cli entry"""
    print('Welcome to janggu (GPL-v2). Copyright (C) 2017 '
          + 'Wolfgang Kopp.')
    APP.run_server()