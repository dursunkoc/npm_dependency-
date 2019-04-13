import sys
from optparse import OptionParser

import requests

from requests.packages import urllib3
urllib3.disable_warnings()

from lxml import html

import networkx as nx
import matplotlib.pyplot as plt
from graphcommons import GraphCommons, Signal, Graph


NPM_REGISTRY_PAGE_URL = 'https://www.npmjs.com/browse/depended'
NPM_PACKAGE_PAGE_URL = 'https://www.npmjs.com/package/'
OFFSET_PARAM = '?offset='
PACKAGES_XPATH = '//section/div[@class="w-80"]/div/a/h3/text()'
DEPS_XPATH = '//section[@id="dependencies"]/ul/li/a/text()'

def npm_registry_url(offset_value):
    if offset_value is None:
        return NPM_REGISTRY_PAGE_URL
    else:
        return f'{NPM_REGISTRY_PAGE_URL}{OFFSET_PARAM}{offset_value}'

def npm_package_url(package_name):
    return f'{NPM_PACKAGE_PAGE_URL}{package_name}?activeTab=dependencies'

def visit(url):
    print(f'access: {url}')
    return requests.get(url, verify=False)

def fetch_registry(offset):
    response = visit(npm_registry_url(offset))
    registry_content = response.content
    registry_html = html.fromstring(registry_content)
    return registry_html.xpath(PACKAGES_XPATH)

def listPackages(number_of_packs):
    packages = []
    next_offset = 0
    while(next_offset < number_of_packs):
        for pack in fetch_registry(next_offset):
            packages.append(pack)
            next_offset = len(packages)
            if next_offset >= number_of_packs:
                break
    return packages

def find_deps(packages):
    package_contents = {package: visit(npm_package_url(package)).text for package in packages}
    package_htmls = {package: html.fromstring(package_content) for package, package_content in package_contents.items()}
    return {package: package_html.xpath(DEPS_XPATH) for package, package_html in package_htmls.items()}

def generate_grid_edgelist(size, depth):
    #TODO use depth for recursive dependencies
    packages = listPackages(size)
    package_deps = find_deps(packages)
    G = nx.DiGraph()
    for package, dependencies in package_deps.items():
        G.add_node(package, type= 'PACKAGE')
        for dependency in dependencies:
            G.add_node(dependency, type= 'PACKAGE')
            G.add_edge(package, dependency, type= 'DEPENDS')
    #TODO complete write to disk
    nx.write_edgelist(G, path="grid.edgelist", delimiter="|")
    return G

def read_generated_grid_edgelist():
    G = nx.read_edgelist(path="grid.edgelist", delimiter="|")
    return G

def new_graph(graphcommons, signals=None, **kwargs):
    if signals is not None:
        kwargs['signals'] = list(map(dict, signals))
    response = graphcommons.make_request('post', 'graphs', data=kwargs)
    return Graph(**response.json()['graph'])


def main(size=None,depth=3):
    graphcommons = GraphCommons('sk_IDfGvifqeRuvQ7HnCcAEsg')
    if size is None:
        G = read_generated_grid_edgelist()
    else:
        G = generate_grid_edgelist(size, depth)
    signals = [Signal(action="node_create", name=node, type=data['type']) for (node, data) in G.nodes(data=True)]
    signals.extend([Signal(action="edge_create", from_name=source, from_type=G.node[source]['type'], to_name=target, to_type=G.node[target]['type'], name=data['type'], weight=1) for source, target, data in G.edges(data=True)])
    created_graph = new_graph(graphcommons, signals=signals, name="NPM Dependency Graph", description="NPM Dependency Graph")
    print ('Created Graph URL:')
    print ('https://graphcommons.com/graphs/%s' % created_graph.id)

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option("-s","--size", dest="size", type=int,
                      help="Size for the first npm fetch")
    parser.add_option("-d","--depth", dest="depth", type=int,
                      help="Max depth of dependencies")
    options, args = parser.parse_args()
    main(options)
