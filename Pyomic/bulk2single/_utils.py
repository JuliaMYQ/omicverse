import pandas as pd
import scanpy
from collections import defaultdict
import numpy as np
from scipy.optimize import nnls
import scanpy as sc
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
from ..utils import pyomic_palette

def bulk2single_data_prepare(bulk_data,single_data,celltype_key):
    r"""
    The data preparation for bulk2single analysis.

    Parameters
    ----------
    - bulk_data : `pandas.DataFrame`
        The bulk-seq data.
    - single_data : `scanpy.AnnData`
        The single cell data.
    - celltype_key : `str`
        The key of cell type in single cell data.

    Returns
    -------
    - input_data : `dict`
        The input data for bulk2single analysis.
    """
    print("...loading data")
    input_data = {}
    
    ism=pd.DataFrame(index=single_data.obs.index)
    ism['Cell']=single_data.obs.index
    ism['Cell_type']=single_data.obs[celltype_key].values
    input_data["input_sc_meta"] = ism
    
    input_data["sc_gene"] = single_data.var._stat_axis.values.tolist()
    input_data["bulk_gene"] = bulk_data._stat_axis.values.tolist()
    
    bulk_genes=input_data["bulk_gene"]
    intersection_genes=[]
    for i in input_data["sc_gene"]:
        if i in bulk_genes:
            intersection_genes.append(i)
    input_data["intersect_gene"] = intersection_genes
    input_data["input_sc_data"] = single_data[:,input_data["intersect_gene"]].to_df().T
    input_data["input_bulk"] = bulk_data.loc[input_data["intersect_gene"]]
    
    return input_data

def bulk2single_plot_cellprop(generate_single_data,celltype_key,figsize=(4,4)):
    r"""
    cellprop plot for bulk2single analysis.

    Parameters
    ----------
    - generate_single_data : `scanpy.AnnData`
        The single cell data generated by bulk2single analysis.
    - celltype_key : `str`
        The key of cell type in single cell data.
    - figsize : `tuple`, optional (default: (4,4))
        The size of figure.

    Returns
    -------
    - ax : `matplotlib.axes.Axes`
        The axes of figure.
    """
    ct_stat = pd.DataFrame(generate_single_data.obs[celltype_key].value_counts())
    ct_name = list(ct_stat.index)
    ct_num = list(ct_stat[celltype_key])
    color = pyomic_palette()
    fig, ax = plt.subplots(figsize=figsize)
    plt.bar(ct_name, ct_num, color=color)
    plt.xticks(ct_name, ct_name, rotation=90)
    plt.title("The number of cells per cell type in bulk-seq data")
    plt.xlabel("Cell type")
    plt.ylabel("Cell number")
    return ax

def bulk2single_plot_correlation(single_data,generate_single_data,celltype_key,
                                 return_table=False,figsize=(6,6),cmap='RdBu_r'):
    r"""
    plot the correlation between input single cell data and generated single cell data.

    Parameters
    ----------
    - single_data : `scanpy.AnnData`
        The input single cell data.
    - generate_single_data : `scanpy.AnnData`
        The single cell data generated by bulk2single analysis.
    - celltype_key : `str`
        The key of cell type in single cell data.
    - return_table : `bool`, optional (default: False)
        Whether to return the correlation table.
    - figsize : `tuple`, optional (default: (6,6))
        The size of figure.
    - cmap : `str`, optional (default: 'RdBu_r')
        The color map of figure.

    Returns
    -------
    ax : `matplotlib.axes.Axes`
        The axes of figure.
    """

    # Calculate 200 marker genes of each cell type
    sc.tl.rank_genes_groups(single_data, celltype_key, method='wilcoxon')
    marker_df = pd.DataFrame(single_data.uns['rank_genes_groups']['names']).head(200)
    #marker = list(set(np.unique(np.ravel(np.array(marker_df))))&set(generate_adata.var.index.tolist()))
    marker = list(set(np.unique(np.ravel(np.array(marker_df))))&set(generate_single_data.var.index.tolist()))

    # the mean expression of 200 marker genes of input sc data
    sc_marker = single_data[:,marker].to_df()
    sc_marker[celltype_key] = single_data.obs[celltype_key]
    sc_marker_mean = sc_marker.groupby(celltype_key)[marker].mean()
    
    # the mean expression of 200 marker genes of deconvoluted bulk-seq data
    #generate_sc_meta.index = list(generate_sc_meta['Cell'])
    generate_sc_data_new = generate_single_data[:,marker].to_df()
    generate_sc_data_new[celltype_key] = generate_single_data.obs[celltype_key]
    generate_sc_marker_mean = generate_sc_data_new.groupby(celltype_key)[marker].mean()

    intersect_cell = list(set(sc_marker_mean.index).intersection(set(generate_sc_marker_mean.index)))
    generate_sc_marker_mean= generate_sc_marker_mean.loc[intersect_cell]
    sc_marker_mean= sc_marker_mean.loc[intersect_cell]

    # calculate correlation
    sc_marker_mean = sc_marker_mean.T
    generate_sc_marker_mean = generate_sc_marker_mean.T

    coeffmat = np.zeros((sc_marker_mean.shape[1], generate_sc_marker_mean.shape[1]))
    for i in range(sc_marker_mean.shape[1]):    
        for j in range(generate_sc_marker_mean.shape[1]):        
            corrtest = pearsonr(sc_marker_mean[sc_marker_mean.columns[i]], 
                                generate_sc_marker_mean[generate_sc_marker_mean.columns[j]])  
            coeffmat[i,j] = corrtest[0]
    if return_table==True:
        return coeffmat
    rf_ct = list(sc_marker_mean.columns)
    generate_ct = list(generate_sc_marker_mean.columns)

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(coeffmat, cmap=cmap)
    ax.set_xticks(np.arange(len(rf_ct)))
    ax.set_xticklabels(rf_ct)
    ax.set_yticks(np.arange(len(generate_ct)))
    ax.set_yticklabels(generate_ct)
    plt.xlabel("scRNA-seq reference")
    plt.ylabel("deconvoluted bulk-seq")
    plt.setp(ax.get_xticklabels(), rotation=90, ha="right", rotation_mode="anchor")
    plt.colorbar(im)
    ax.set_title("Expression correlation")
    fig.tight_layout()
    return ax



def load_data(input_bulk_path,
              input_sc_data_path,
              input_sc_meta_path,):
    input_sc_meta_path = input_sc_meta_path
    input_sc_data_path = input_sc_data_path
    input_bulk_path = input_bulk_path
    print("loading data......")
    input_data = {}
    # load sc_meta.csv file, containing two columns of cell name and cell type
    input_data["input_sc_meta"] = pd.read_csv(input_sc_meta_path, index_col=0)
    # load sc_data.csv file, containing gene expression of each cell
    input_sc_data = pd.read_csv(input_sc_data_path, index_col=0)
    input_data["sc_gene"] = input_sc_data._stat_axis.values.tolist()
    # load bulk.csv file, containing one column of gene expression in bulk
    input_bulk = pd.read_csv(input_bulk_path, index_col=0)
    input_data["bulk_gene"] = input_bulk._stat_axis.values.tolist()
    # filter overlapping genes.
    bulk_genes=input_data["bulk_gene"]
    intersection_genes=[]
    for i in input_data["sc_gene"]:
        if i in bulk_genes:
            intersection_genes.append(i)
    
    input_data["intersect_gene"] = intersection_genes
    input_data["input_sc_data"] = input_sc_data.loc[input_data["intersect_gene"]]
    input_data["input_bulk"] = input_bulk.loc[input_data["intersect_gene"]]
    # load st_meta.csv and st_data.csv, containing coordinates and gene expression of each spot respectively.
    #input_data["input_st_meta"] = pd.read_csv(input_st_meta_path, index_col=0)
    #input_data["input_st_data"] = pd.read_csv(input_st_data_path, index_col=0)
    print("load data done!")
    
    return input_data


def data_process(data, top_marker_num, ratio_num):
    # marker used
    sc = scanpy.AnnData(data["input_sc_data"].T)
    sc.obs = data["input_sc_meta"][['Cell_type']]
    scanpy.tl.rank_genes_groups(sc, 'Cell_type', method='wilcoxon')
    marker_df = pd.DataFrame(sc.uns['rank_genes_groups']['names']).head(top_marker_num)
    marker_array = np.array(marker_df)
    marker_array = np.ravel(marker_array)
    marker_array = np.unique(marker_array)
    marker = list(marker_array)
    sc_marker = data["input_sc_data"].loc[marker, :]
    bulk_marker = data["input_bulk"].loc[marker]

    #  Data processing
    breed = data["input_sc_meta"]['Cell_type']
    breed_np = breed.values
    breed_set = set(breed_np)
    id2label = sorted(list(breed_set))  # List of breed
    label2id = {label: idx for idx, label in enumerate(id2label)}  # map breed to breed-id

    cell2label = dict()  # map cell-name to breed-id
    label2cell = defaultdict(set)  # map breed-id to cell-names
    for row in data["input_sc_meta"].itertuples():
        cell_name = getattr(row, 'Cell')
        cell_type = label2id[getattr(row, 'Cell_type')]
        cell2label[cell_name] = cell_type
        label2cell[cell_type].add(cell_name)

    label_devide_data = dict()
    for label, cells in label2cell.items():
        label_devide_data[label] = sc_marker[list(cells)]

    single_cell_splitby_breed_np = {}
    for key in label_devide_data.keys():
        single_cell_splitby_breed_np[key] = label_devide_data[key].values  # [gene_num, cell_num]
        single_cell_splitby_breed_np[key] = single_cell_splitby_breed_np[key].mean(axis=1)

    max_decade = len(single_cell_splitby_breed_np.keys())
    single_cell_matrix = []

    for i in range(max_decade):
        single_cell_matrix.append(single_cell_splitby_breed_np[i].tolist())

    single_cell_matrix = np.array(single_cell_matrix)
    single_cell_matrix = np.transpose(single_cell_matrix)  # (gene_num, label_num)

    bulk_marker = bulk_marker.values  # (gene_num, 1)
    bulk_rep = bulk_marker.reshape(bulk_marker.shape[0], )

    # calculate celltype ratio in each spot by NNLS
    ratio = nnls(single_cell_matrix, bulk_rep)[0]
    ratio = ratio / sum(ratio)

    ratio_array = np.round(ratio * data["input_sc_meta"].shape[0] * ratio_num)
    ratio_list = [r for r in ratio_array]

    cell_target_num = dict(zip(id2label, ratio_list))

    return cell_target_num



