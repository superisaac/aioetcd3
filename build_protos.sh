#!/bin/bash

function cproto() {
    protopath=$1
    package=$2
    genrpc=$3
    protodir=`dirname $protopath`

    outdir=./aioetcd3/pb/$package/
    mkdir -p $outdir
    touch $outdir/__init__.py

    echo Compiling `basename $protopath`
    if [ "genrpc$genrpc" == "genrpctrue" ]; then
        python -m grpc_tools.protoc -I $protodir \
               --proto_path="$proto_path" \
               --python_out=$outdir \
               --grpclib_python_out=$outdir \
               $protopath
    else
        python -m grpc_tools.protoc -I $protodir \
               --proto_path="$proto_path" \
               --python_out=$outdir \
               $protopath
    fi
}

cproto ./proto/auth.proto authpb
cproto ./proto/kv.proto mvccpb
cproto ./proto/rpc.proto etcdserverpb true

# replace imports
for f in $(find aioetcd3/pb -name '*_pb2.py' -or -name '*_grpc.py')
do
    sed -ie 's/import kv_pb2/from aioetcd3.pb.mvccpb import kv_pb2/g' $f
    sed -ie 's/import auth_pb2/from aioetcd3.pb.authpb import auth_pb2/g' $f
    sed -ie 's/import rpc_pb2/from aioetcd3.pb.etcdserverpb import rpc_pb2/g' $f
done

# delete sed caches
find aioetcd3/pb -name '*.pye' | xargs rm

# touch __init__.py files
for dir in $(find ./aioetcd3 -type d)
do
    touch $dir/__init__.py
done
