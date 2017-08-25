from os import listdir
from os.path import isfile, join

import yaml
import json

def getGraphvizDotFormat(graph):
	nodes = graph.nodes()
	edges = graph.edges()

	content = "digraph {\n"
	for u in nodes:
		if u in edges:
			for v in edges[u]:
				content += "\"%s\" -> \"%s\";\n" % (u.replace('-', '_'), v.replace('-', '_'))

	for node in nodes:
		content += "\"%s\" [style=filled, fillcolor=orange]\n" % node.replace('-', '_')

	content += "}\n"
	return content

class Graph(object):

	def __init__(self, nodes = set([]), edges = {}):
		self._nodes = nodes
		self._edges = edges

	def nodes(self):
		return self._nodes

	def edges(self):
		return self._edges

	def __str__(self):
		return json.dumps({
			"nodes": list(self._nodes),
			"edges": self._edges
})

def name2node(name):
	if name.startswith("common/test_cases"):
		name = "C/TC/\n{}".format(name[18:])

	if name.startswith("common/test_suites"):
		name = "C/TS/\n{}".format(name[19:])

	if name.startswith("test_cases"):
		name = "TC/\n{}".format(name[11:])

	if name.startswith("test_suites"):
		name = "TS\n/{}".format(name[12:])

	if name.endswith(".yml"):
		return name[:-4]
	return name

def constructSubgraph(dir, graph):
	nodes = graph.nodes()
	edges = graph.edges()

	for f in listdir(dir):
		filepath = join(dir, f)
		if not isfile(filepath):
			continue

		node = name2node(filepath)
		nodes.add(node)
		with open(filepath, "r") as f:
			data = yaml.load(f)

		if "children" in data:
			for child in data["children"]:
				childpath = join("test_cases", child)
				childnode = name2node(childpath)
				nodes.add(childnode)
				try:
					edges[node].append(childnode)
				except KeyError:
					edges[node] = [childnode]

		if "parent" in data:
			parentnode = name2node(data["parent"])
			try:
				edges[node].append(parentnode)
			except KeyError:
				edges[node] = [parentnode]

graph = Graph()

constructSubgraph("common/test_suites", graph)
constructSubgraph("common/test_cases", graph)
constructSubgraph("test_suites", graph)
constructSubgraph("test_cases", graph)

print getGraphvizDotFormat(graph)
