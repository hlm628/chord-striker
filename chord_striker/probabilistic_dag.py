import networkx as nx
from random import choices
import pydot


class ProbDAG:
    def __init__(self, directed_graph):
        """
        A class to represent a probabilistic directed acyclic graph (DAG).
        The graph must be weakly connected, and have a unique source and sink node.
        Each edge must have a probability assigned to it, and the outgoing probabilities
        from each node (except the sink) must sum to 1.
        """
        # check graph is a DiGraph
        if not isinstance(directed_graph, nx.DiGraph):
            raise TypeError("directed_graph must be a DiGraph object")

        # check weakly connected
        if not nx.is_weakly_connected(directed_graph):
            raise ValueError("directed_graph must be connected")

        # check for cycles
        if not nx.is_directed_acyclic_graph(directed_graph):
            raise ValueError("directed_graph must be acyclic")

        ## check for sink/source

        # topologically sort graph
        ts_nodes = list(nx.topological_sort(directed_graph))

        if ts_nodes == []:
            raise ValueError("directed_graph must have at least one node")

        # source must be first node, sink must be last
        possible_source, possible_sink = ts_nodes[0], ts_nodes[-1]

        # source (sink) must have every other node as a descendant (ancestor)
        possible_source_descendants = nx.descendants(directed_graph, possible_source)

        source_test = True

        for node in ts_nodes[1:]:
            if node not in possible_source_descendants:
                source_test = False

        if not source_test:
            raise ValueError("directed_graph must have a unique source node")

        # similarly for sink
        possible_sink_ancestors = nx.ancestors(directed_graph, possible_sink)

        sink_test = True

        for node in ts_nodes[:-1]:
            if node not in possible_sink_ancestors:
                sink_test = False

        if not sink_test:
            raise ValueError("directed_graph must have a unique sink node")

        # check probabilities for all but the sink node
        for node in ts_nodes[:-1]:
            successor_nodes = directed_graph.successors(node)

            # check there is a probability for each edge

            outgoing_probabilities = []

            for successor in successor_nodes:
                edge_attributes = directed_graph.get_edge_data(node, successor)

                if "p" not in edge_attributes:
                    raise ValueError(
                        "every edge in directed_graph must have a probability assigned"
                    )

                p = edge_attributes["p"]

                if not isinstance(p, (int, float)):
                    raise ValueError(
                        "probability must be a real number between 0 (exclusive) and 1 (inclusive)"
                    )

                if p < 0 or p > 1:
                    raise ValueError(
                        "probability must be a real number between 0 (exclusive) and 1 (inclusive)"
                    )

                outgoing_probabilities.append(p)

            # now check outgoing probabilities sum to 1:
            if round(sum(outgoing_probabilities), 5) != 1:
                raise ValueError(
                    "outgoing probabilities from node {} must sum to 1; instead they sum to {}".format(
                        node, sum(outgoing_probabilities)
                    )
                )

        # if all tests have been based, this is our graph object
        self.__graph = directed_graph

        # we also save source and sink objects
        self.__source = possible_source
        self.__sink = possible_sink

    def get_node_attributes(self, attr):
        """Method of getting a dictionary of format node:value where node[attr] = value."""

        if not isinstance(attr, str):
            raise TypeError("attr must be a string")

        attr_dict = dict()

        for node in self.__graph.nodes:
            node_attributes = self.__graph.nodes[node]
            if not attr in node_attributes:
                raise ValueError("node {} has no value for key {}".format(node, attr))
            attr_dict[node] = node_attributes[attr]

        return attr_dict

    def get_random_path(self):
        """A method to pick a random path through the graph, using the probabilities assigned to edges."""

        path = [self.__source]

        current_node = self.__source

        while current_node != self.__sink:
            # get successor data from graph
            successors = [
                (successor, self.__graph.get_edge_data(current_node, successor)["p"])
                for successor in self.__graph.successors(current_node)
            ]

            # split into the nodes themselves and their probabilities
            successor_nodes, successor_probs = [s[0] for s in successors], [
                s[1] for s in successors
            ]

            # sample
            current_node = choices(successor_nodes, weights=successor_probs)[0]

            path.append(current_node)

        return path

    def write_graphviz(self, filepath):
        """Write the graph to a PNG file using Graphviz."""
        graph_copy = self.__graph.copy()
        edge_labels = {
            (u, v): f"{data['p']:.2f}" for u, v, data in graph_copy.edges(data=True)
        }
        nx.set_edge_attributes(graph_copy, edge_labels, "label")

        # Create a Pydot graph
        pydot_graph = nx.drawing.nx_pydot.to_pydot(graph_copy)

        # Set graph attributes for better visualization
        pydot_graph.set_rankdir("TB")  # Top to bottom layout
        pydot_graph.set_node_defaults(shape="box", style="rounded")

        # Save as PNG
        pydot_graph.write_png(filepath)
