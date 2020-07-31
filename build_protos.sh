#!/bin/bash

ETCDREPO=./tmp/etcd
GWREPO=./tmp/grpc-gateway

mkdir -p ./tmp

if [ ! -f $ETCDREPO/README.md ]; then
    echo clone etcd repo
    git clone https://github.com/etcd-io/etcd.git $ETCDREPO
fi

if [ ! -f $GWREPO/README.md ]; then
    echo clone grpc-gateway repo
    git clone https://github.com/grpc-ecosystem/grpc-gateway.git $GWREPO
fi

proto_path="./tmp:$ETCDREPO:$ETCDREPO/vendor:$ETCDREPO/vendor/google.golang.org/genproto/protobuf:$ETCDREPO/vendor/github.com/gogo/protobuf:$ETCDREPO/vendor/github.com/golang/protobuf:$GWREPO/third_party/googleapis"

function cproto() {
    protopath=$1
    package=$2
    protodir=`dirname $protopath`

    outdir=./aioetcd3/pb/$package/
    mkdir -p $outdir
    touch $outdir/__init__.py
    
    echo Compiling `basename $protopath`
    python -m grpc_tools.protoc -I $protodir \
           --proto_path="$proto_path" \
           --python_out=$outdir \
           --grpclib_python_out=$outdir \
           $protopath
}

#cproto $GWREPO/third_party/googleapis/google/api/annotations.proto google/api
cproto $ETCDREPO/vendor/github.com/gogo/protobuf/gogoproto/gogo.proto gogoproto
cproto $ETCDREPO/mvcc/mvccpb/kv.proto etcd/mvcc/mvccpb
cproto $ETCDREPO/auth/authpb/auth.proto etcd/auth/authpb
cproto $ETCDREPO/etcdserver/etcdserverpb/rpc.proto etcdserverpb
cproto $ETCDREPO/etcdserver/etcdserverpb/etcdserver.proto etcdserverpb

for f in $(find aioetcd3/pb -name '*_pb2.py' -or -name '*_grpc.py')
do
    sed -ie 's/from etcd/from aioetcd.pb.etcd/g' $f
    sed -ie 's/from gogoproto/from aioetcd.pb.gogoproto/g' $f
    sed -ie 's/from etcdserverpb/from aioetcd.pb.etcdserverpb/g' $f
    sed -ie 's/import etcd/import aioetcd.pb.etcd/g' $f
    sed -ie 's/import gogoproto/import aioetcd.pb.gogoproto/g' $f
    sed -ie 's/import etcdserverpb/import aioetcd.pb.etcdserverpb/g' $f    
done

find aioetcd3/pb -name '*.pye' | xargs rm 

for dir in $(find aioetcd3 -type d)
do
    touch $dir/__init__.py
done


