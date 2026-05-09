import json

nodes = []
edges = []

with open('graph_export.jsonl', 'r') as f:
    for line in f:
        item = json.loads(line)
        if 'type' in item:
            # It's a node
            node_id = item['data']['id']
            label = item['data'].get('name', item['data'].get('event_id', node_id))
            nodes.append({
                "id": node_id,
                "label": label,
                "group": item['type'],
                "title": f"Type: {item['type']}\nData: {json.dumps(item['data'], indent=2)}"
            })
        elif 'edge' in item:
            # It's an edge
            edges.append({
                "from": item['from'],
                "to": item['to'],
                "label": item['edge']
            })

html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Omnigraph Visualization</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        #mynetwork {{
            width: 100%;
            height: 800px;
            border: 1px solid lightgray;
        }}
        body {{ font-family: sans-serif; }}
    </style>
</head>
<body>
    <h2>Omnigraph: crm-fixed (main branch)</h2>
    <div id="mynetwork"></div>
    <script type="text/javascript">
        var nodes = new vis.DataSet({json.dumps(nodes)});
        var edges = new vis.DataSet({json.dumps(edges)});

        var container = document.getElementById('mynetwork');
        var data = {{
            nodes: nodes,
            edges: edges
        }};
        var options = {{
            nodes: {{
                shape: 'dot',
                size: 16
            }},
            physics: {{
                forceAtlas2Based: {{
                    gravitationalConstant: -26,
                    centralGravity: 0.005,
                    springLength: 230,
                    springConstant: 0.18
                }},
                maxVelocity: 146,
                solver: 'forceAtlas2Based',
                timestep: 0.35,
                stabilization: {{ iterations: 150 }}
            }},
            groups: {{
                Account: {{ color: {{ background: 'blue', border: 'darkblue' }}, font: {{ color: 'blue' }} }},
                AccountEvent: {{ color: {{ background: 'orange', border: 'darkorange' }}, font: {{ color: 'orange' }} }}
            }}
        }};
        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""

with open('graph_viz.html', 'w') as f:
    f.write(html_content)

print(f"Visualization generated: graph_viz.html with {len(nodes)} nodes and {len(edges)} edges.")
