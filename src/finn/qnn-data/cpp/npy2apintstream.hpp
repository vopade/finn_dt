#include <iostream>
#include "cnpy.h"
#include "hls_stream.h"
#include "ap_int.h"
#include <vector>
#include <stdio.h>
#include <hls_vector.h>
#include "interpret_bipolar.hpp"
#include <type_traits>


#define DEBUG
#ifdef DEBUG
#define DEBUG_NPY2APINTSTREAM(x) std::cerr << "[npy2apintstream] " << x << std::endl;
#define DEBUG_APINTSTREAM2NPY(x) std::cerr << "[apintstream2npy] " << x << std::endl;
#else
#define DEBUG_NPY2APINTSTREAM(x) ;
#define DEBUG_APINTSTREAM2NPY(x) ;
#endif

template <typename PackedT, typename ElemT, int ElemBits, typename NpyT>
void npy2apintstream(const char * npy_path, hls::stream<PackedT> & out_stream, bool reverse_inner = true, size_t numReps = 1) {
    DEBUG_APINTSTREAM2NPY("This is npy2apintstream and not supposed to be called")
  for(size_t rep = 0; rep < numReps; rep++) {
    cnpy::NpyArray arr = cnpy::npy_load(npy_path);
    DEBUG_NPY2APINTSTREAM("word_size " << arr.word_size << " num_vals " << arr.num_vals)
    if(arr.word_size != sizeof(NpyT)) {
      throw "Npy array word size and specified NpyT size do not match";
    }
    NpyT* loaded_data = arr.data<NpyT>();
    size_t outer_dim_elems = 1;
    for(size_t dim = 0; dim < arr.shape.size()-1; dim++) {
      outer_dim_elems *= arr.shape[dim];
    }
    size_t inner_dim_elems = arr.shape[arr.shape.size()-1];
    DEBUG_NPY2APINTSTREAM("n_outer " << outer_dim_elems << " n_inner " << inner_dim_elems)
    for(size_t outer_elem = 0; outer_elem < outer_dim_elems; outer_elem++) {
      PackedT packed_elem = 0;
      for(size_t ii = 0; ii < inner_dim_elems; ii++) {
        size_t i = reverse_inner ? inner_dim_elems-ii-1 : ii;
        NpyT loaded_elem_npyt = *loaded_data;
        ElemT loaded_elem = (ElemT) loaded_elem_npyt;
        DEBUG_NPY2APINTSTREAM("NpyT " << loaded_elem_npyt << " elem " << loaded_elem)
        packed_elem((i+1)*ElemBits-1, i*ElemBits) = *reinterpret_cast<ap_uint<ElemBits>*>(&loaded_elem);
        loaded_data++;
      }
      DEBUG_NPY2APINTSTREAM("packed hls elem " << std::hex << packed_elem << std::dec)
      out_stream << packed_elem;
    }
  }
}

template <typename PackedT, typename ElemT, int ElemBits, typename NpyT>
void apintstream2npy(hls::stream<PackedT> & in_stream, const std::vector<size_t> & shape, const char * npy_path, bool reverse_inner = true, size_t numReps = 1, size_t multi_pixel_out = 1) {
  for(size_t rep = 0; rep < numReps; rep++) {
    std::vector<NpyT> data_to_save;
    size_t outer_dim_elems = 1;
    for(size_t dim = 0; dim < shape.size()-1; dim++) {
      outer_dim_elems *= shape[dim];
    }
    size_t inner_dim_elems = shape[shape.size()-1] / multi_pixel_out;
    DEBUG_APINTSTREAM2NPY("n_outer " << outer_dim_elems << " n_inner " << inner_dim_elems << " n_multi_pixel_out " << multi_pixel_out)
    for(size_t outer_elem = 0; outer_elem < outer_dim_elems; outer_elem++) {
      PackedT packed_elem;
      in_stream >> packed_elem;
      DEBUG_APINTSTREAM2NPY("packed hls elem " << std::hex << packed_elem << std::dec)
      for(size_t ii_multi_pixel_out = 0; ii_multi_pixel_out < multi_pixel_out; ii_multi_pixel_out++) {
        // loop over multi_pixel_out blocks of inner_dim_elems separately,
        // so that reverse_inner is not applied across multiple pixels
        for(size_t ii = 0; ii < inner_dim_elems; ii++) {
          size_t i = ii_multi_pixel_out*inner_dim_elems;
          i += reverse_inner ? inner_dim_elems-ii-1 : ii;
          ap_uint<ElemBits> tmp_elem = packed_elem((i+1)*ElemBits-1, i*ElemBits);
          // important: don't init elem = reinterpret_cast.. directly here
          // this causes weird behavior for conversion to NpyT afterwards
          ElemT elem;
          elem = reinterpret_cast<ElemT&>(tmp_elem);
          NpyT npyt = (NpyT) elem;
          DEBUG_APINTSTREAM2NPY("elem " << elem << " NpyT " << npyt)
          data_to_save.push_back(npyt);
        }
      }
    }
    cnpy::npy_save(npy_path, &data_to_save[0], shape, "w");
  }
}


template <typename ElemT, typename NpyT, unsigned N>
void npy2apintvectorstream(const char * npy_path, hls::stream<hls::vector<ElemT,N>> & out_stream, bool reverse_inner = true, size_t numReps = 1) {
    DEBUG_APINTSTREAM2NPY("This is npy2apintvectorstream")

    if (std::is_same<ElemT, Bipolar>::value)
      DEBUG_APINTSTREAM2NPY("Elem is Bipolar, npy path: " << npy_path)
  // input to operator
  for(size_t rep = 0; rep < numReps; rep++) {
    cnpy::NpyArray arr = cnpy::npy_load(npy_path);
    DEBUG_NPY2APINTSTREAM("word_size " << arr.word_size << " num_vals " << arr.num_vals)
    if(arr.word_size != sizeof(NpyT)) {
      throw "Npy array word size and specified NpyT size do not match";
    }
    NpyT* loaded_data = arr.data<NpyT>(); // always float
    size_t outer_dim_elems = 1;
    for(size_t dim = 0; dim < arr.shape.size()-1; dim++) {
      outer_dim_elems *= arr.shape[dim];
    }

    size_t inner_dim_elems = arr.shape[arr.shape.size()-1];

    DEBUG_NPY2APINTSTREAM("n_outer " << outer_dim_elems << " n_inner " << inner_dim_elems)
    for(size_t outer_elem = 0; outer_elem < outer_dim_elems; outer_elem++)
    {
      hls::vector<ElemT, N> vec;
      for(size_t ii = 0; ii < inner_dim_elems; ii++) {
        ElemT elem = loaded_data[outer_elem*inner_dim_elems+ii]; // cast to uint
        DEBUG_NPY2APINTSTREAM("npy2 elem: " << elem << ", loaded data: " << loaded_data[outer_elem*inner_dim_elems+ii])
        vec[ii] = elem;
      }
      out_stream << vec;
    }
  }
}


/*
template <Bipolar ElemT, typename NpyT, unsigned N>
void npy2apintvectorstream(const char * npy_path, hls::stream<hls::vector<ElemT,N>> & out_stream, bool reverse_inner = true, size_t numReps = 1) 
{
  //  error: non-type template parameters of class type only available with ‘-std=c++20’ or ‘-std=gnu++20’
  npy2apintvectorstream<ap_uint<1>, NpyT, N>(npy_path, out_stream, reverse_inner, numReps);
}
*/

template <typename ElemT, typename NpyT, unsigned N>
void apintvectorstream2npy(hls::stream<hls::vector<ElemT,N>> & in_stream, const std::vector<size_t> & shape, const char * npy_path, bool reverse_inner = true, size_t numReps = 1, size_t multi_pixel_out = 1) {
  DEBUG_APINTSTREAM2NPY("This is apintvectorstream2npy")
  for(size_t rep = 0; rep < numReps; rep++) {
    std::vector<NpyT> data_to_save;
    size_t outer_dim_elems = 1;
    for(size_t dim = 0; dim < shape.size()-1; dim++) {
      outer_dim_elems *= shape[dim];
    }
    size_t inner_dim_elems = shape[shape.size()-1] / multi_pixel_out;
    DEBUG_APINTSTREAM2NPY("n_outer " << outer_dim_elems << " n_inner " << inner_dim_elems << " n_multi_pixel_out " << multi_pixel_out)
    for(size_t outer_elem = 0; outer_elem < outer_dim_elems; outer_elem++) {
      //in_stream >> packed_elem; // change this
      for(size_t ii_multi_pixel_out = 0; ii_multi_pixel_out < multi_pixel_out; ii_multi_pixel_out++) {
        // loop over multi_pixel_out blocks of inner_dim_elems separately,
        // so that reverse_inner is not applied across multiple pixels
        hls::vector<ElemT, N> results;
        in_stream >> results;
        for(size_t ii = 0; ii < inner_dim_elems; ii++) {
          size_t i = ii_multi_pixel_out*inner_dim_elems;
          i += reverse_inner ? inner_dim_elems-ii-1 : ii;

        NpyT npyt = (NpyT) results[i];
        //DEBUG_APINTSTREAM2NPY("results[i] " << results[i] << " NpyT " << npyt)
        data_to_save.push_back(npyt);
        }
      }
    }
    cnpy::npy_save(npy_path, &data_to_save[0], shape, "w");
  }
}
