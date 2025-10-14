#!/usr/bin/env python3
"""
Created on Oct 10 2025
@author: Gehan Ranepura

Name: rename_water_chains.py
Align a PDB file with waters onto a reference PDB, then assign chain IDs to waters based on nearest protein chain.
"""

from Bio.PDB import PDBParser, Superimposer, NeighborSearch
import numpy as np
import warnings
from Bio.PDB.PDBExceptions import PDBConstructionWarning

# Suppress warnings about discontinuous chains
warnings.simplefilter('ignore', PDBConstructionWarning)

def get_ca_atoms(structure):
    """Extract all CA atoms from a structure for alignment."""
    ca_atoms = []
    for model in structure:
        for chain in model:
            for residue in chain:
                if residue.id[0] == ' ' and 'CA' in residue:
                    ca_atoms.append(residue['CA'])
    return ca_atoms

def align_structures(reference_structure, hydrated_structure):
    """
    Align reference structure onto hydrated structure using CA atoms.
    """
    # Get CA atoms from both structures
    ref_ca = get_ca_atoms(reference_structure)
    hydrated_ca = get_ca_atoms(hydrated_structure)
    
    # Ensure same number of CA atoms
    min_len = min(len(ref_ca), len(hydrated_ca))
    if len(ref_ca) != len(hydrated_ca):
        print(f"Warning: Different number of CA atoms. Using first {min_len} atoms.")
        ref_ca = ref_ca[:min_len]
        hydrated_ca = hydrated_ca[:min_len]
    
    # Perform superimposition - align reference TO hydrated
    super_imposer = Superimposer()
    super_imposer.set_atoms(hydrated_ca, ref_ca)
    
    # Apply transformation to all atoms in reference structure
    super_imposer.apply(reference_structure.get_atoms())
    
    print(f"Alignment RMSD: {super_imposer.rms:.3f} Å")

def assign_chain_ids(hydrated_structure, reference_structure):
    """
    Assign chain IDs to all residues in hydrated structure based on reference.
    Preserves original atom order.
    """
    # Get all protein residues from reference with chain IDs (in order)
    ref_residues_with_chains = []
    for model in reference_structure:
        for chain in model:
            for residue in chain:
                if residue.id[0] == ' ':  # Standard residue
                    ref_residues_with_chains.append(chain.id)
    
    # Get all residues from hydrated (in order), separating protein and water
    hydrated_protein_residues = []
    hydrated_water_residues = []
    
    for model in hydrated_structure:
        for chain in model:
            for residue in chain:
                # Check if it's a water first
                if residue.resname in ['HOH', 'WAT', 'H2O', 'TIP3']:
                    hydrated_water_residues.append(residue)
                elif residue.id[0] == ' ':  # Standard protein residue (not water)
                    hydrated_protein_residues.append(residue)
    
    print(f"Reference structure: {len(ref_residues_with_chains)} protein residues")
    print(f"Hydrated structure: {len(hydrated_protein_residues)} protein residues, {len(hydrated_water_residues)} waters")
    
    # Create mapping: residue -> chain_id
    residue_to_chain = {}
    
    # Check if protein residue counts match
    if len(ref_residues_with_chains) != len(hydrated_protein_residues):
        print(f"Warning: Different number of protein residues!")
        min_len = min(len(ref_residues_with_chains), len(hydrated_protein_residues))
    else:
        min_len = len(ref_residues_with_chains)
    
    # Assign protein residues
    for i in range(min_len):
        residue_to_chain[hydrated_protein_residues[i]] = ref_residues_with_chains[i]
    
    print(f"Assigned chain IDs to {min_len} protein residues")
    
    # Now assign waters based on nearest protein atom
    # Get all protein atoms with their chain IDs
    protein_atoms = []
    atom_to_chain = {}
    
    for residue in hydrated_protein_residues[:min_len]:
        chain_id = residue_to_chain[residue]
        for atom in residue:
            protein_atoms.append(atom)
            atom_to_chain[atom] = chain_id
    
    # Create NeighborSearch
    ns = NeighborSearch(protein_atoms)
    
    # Assign waters
    water_count = 0
    chain_assignments = {}
    
    for residue in hydrated_water_residues:
        water_count += 1
        
        # Get oxygen atom coordinates
        water_coord = None
        for atom in residue:
            if atom.name in ['O', 'OW', 'OH2']:
                water_coord = atom.coord
                break
        if water_coord is None and len(list(residue.get_atoms())) > 0:
            water_coord = list(residue.get_atoms())[0].coord
        
        if water_coord is not None:
            # Find nearest protein atom
            nearest = ns.search(water_coord, 20.0, level='A')
            
            if nearest:
                distances = [np.linalg.norm(water_coord - atom.coord) 
                           for atom in nearest]
                min_idx = np.argmin(distances)
                closest_atom = nearest[min_idx]
                closest_chain_id = atom_to_chain[closest_atom]
                
                residue_to_chain[residue] = closest_chain_id
                
                if closest_chain_id not in chain_assignments:
                    chain_assignments[closest_chain_id] = 0
                chain_assignments[closest_chain_id] += 1
    
    print(f"Assigned chain IDs to {water_count} water molecules")
    print("Waters per chain:")
    for chain_id in sorted(chain_assignments.keys()):
        print(f"  Chain {chain_id}: {chain_assignments[chain_id]} waters")
    
    return residue_to_chain

def write_pdb_with_chain_ids(structure, residue_to_chain, output_file):
    """
    Write PDB file with updated chain IDs while preserving atom order.
    """
    with open(output_file, 'w') as f:
        atom_number = 1
        
        for model in structure:
            for chain in model:
                for residue in chain:
                    # Get the chain ID for this residue
                    chain_id = residue_to_chain.get(residue, chain.id)
                    
                    for atom in residue:
                        # Write ATOM/HETATM record
                        record_type = "ATOM  " if residue.id[0] == ' ' else "HETATM"
                        
                        line = f"{record_type}{atom_number:5d} {atom.name:^4s} {residue.resname:3s} {chain_id:1s}{residue.id[1]:4d}    "
                        line += f"{atom.coord[0]:8.3f}{atom.coord[1]:8.3f}{atom.coord[2]:8.3f}"
                        line += f"{atom.occupancy:6.2f}{atom.bfactor:6.2f}          {atom.element:>2s}\n"
                        
                        f.write(line)
                        atom_number += 1
        
        f.write("END\n")

def main():
    import argparse
    import os
    
    # Set up argument parser
    parser_args = argparse.ArgumentParser(
        description='Align reference PDB to hydrated PDB and assign chain IDs to waters.'
    )
    parser_args.add_argument('reference_pdb', 
                            help='Reference PDB file (without waters)')
    parser_args.add_argument('hydrated_pdb', 
                            help='PDB file with waters')
    
    args = parser_args.parse_args()
    
    reference_pdb = args.reference_pdb
    hydrated_pdb = args.hydrated_pdb
    
    # Create output filename
    base_name = os.path.splitext(hydrated_pdb)[0]
    output_pdb = f"{base_name}_altered.pdb"
    
    # Initialize parser
    parser = PDBParser(QUIET=True)
    
    # Load structures
    print(f"Loading reference structure: {reference_pdb}")
    ref_structure = parser.get_structure("reference", reference_pdb)
    
    print(f"Loading hydrated structure: {hydrated_pdb}")
    hydrated_structure = parser.get_structure("hydrated", hydrated_pdb)
    
    # Align reference onto hydrated
    print("\nAligning reference structure onto hydrated structure...")
    align_structures(ref_structure, hydrated_structure)
    
    # Assign chain IDs
    print("\nAssigning chain IDs...")
    residue_to_chain = assign_chain_ids(hydrated_structure, ref_structure)
    
    # Save output with preserved atom order
    print(f"\nSaving output to: {output_pdb}")
    write_pdb_with_chain_ids(hydrated_structure, residue_to_chain, output_pdb)
    
    print("Done!")

if __name__ == "__main__":
    main()
