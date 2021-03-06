#Copyright (C) 2016-2019 Andreas Mayr, Guenter Klambauer, Thomas Unterthiner, Sepp Hochreiter
#Licensed under original BSD License (see LICENSE-ExCAPE at base directory) for members of the Horizon 2020 Project ExCAPE (Grant Agreement no. 671555)
#Licensed under GNU General Public License v3.0 (see LICENSE at base directory) for the general public

actLib=imp.load_source(basePath+'actLib.py', basePath+"actLib.py")



nrLayers=hyperParams.iloc[paramNr].nrLayers
nrStart=hyperParams.iloc[paramNr].nrStart
layerForm=hyperParams.iloc[paramNr].layerForm
basicArchitecture=hyperParams.iloc[paramNr].basicArchitecture

nrInputFeatures=nrDenseFeatures+nrSparseFeatures

if(layerForm=="rect"):
  hiddenLayerSizes = [nrStart] * nrLayers
elif(layerForm=="cone"):
  hiddenLayerSizes = (nrStart * np.power(np.power(float(nrOutputTargets)/float(nrStart), 1./float(nrLayers)), range(0, nrLayers))).astype(int).tolist()
elif(layerForm=="diavolo"):
  if (nrLayers % 2 == 0):
    qq = np.power(float(nrOutputTargets)/float(nrStart), 1./(float(nrLayers)/2.))
    hiddenLayerSizes = np.concatenate([(nrStart * np.power(qq, range(0, int(float(nrLayers)/2.)))), (nrOutputTargets * np.power(1.0/qq, range(1, int(float(nrLayers)/2.)+1)))]).astype(int).tolist()
  else:
    qq = np.power(float(nrOutputTargets)/float(nrStart), 1./((float(nrLayers)-1.)/2.))
    hiddenLayerSizes = np.concatenate([(nrStart * np.power(qq, range(0, int(float(nrLayers)/2.)))), (nrOutputTargets * np.power(1.0/qq, range(0, int(float(nrLayers)/2.)+1)))]).astype(int).tolist()
layerSizes=[nrInputFeatures]+hiddenLayerSizes+[nrOutputTargets]

if basicArchitecture[1]=="selu":
  activationFunction=actLib.selu
  dropoutFunction=actLib.dropout_selu
  idropoutFunction=actLib.dropout_stableVariance
  initScale=1.0
elif basicArchitecture[1]=="relu":
  activationFunction=tf.nn.relu
  dropoutFunction=actLib.dropout_relu
  idropoutFunction=actLib.dropout_relu
  initScale=2.0
elif basicArchitecture[1]=="elu":
  activationFunction=tf.nn.elu
  dropoutFunction=actLib.dropout_relu
  idropoutFunction=actLib.dropout_relu
  initScale=1.55



tf.reset_default_graph()
if "session" in dir():
  session.close()
gpu_options=tf.GPUOptions(allow_growth=True)
session=tf.InteractiveSession(config=tf.ConfigProto(gpu_options=gpu_options))



if nrDenseFeatures>0.5:
  xDenseData=tf.placeholder(tf.float32, [None, nrDenseFeatures])
if nrSparseFeatures>0.5:
  xIndices = tf.placeholder(tf.int64, [None, 2])
  xValues = tf.placeholder(tf.float32, [None])
  xDim = tf.placeholder(tf.int64, [2])
  xSparseData=tf.SparseTensor(indices=xIndices, values=xValues, dense_shape=xDim)
  sparseMeanInit=tf.placeholder(tf.float32, [1, nrSparseFeatures])
  sparseMean=tf.Variable(tf.zeros([1, nrSparseFeatures]), trainable=False, dtype=tf.float32)



yDenseData=tf.placeholder(tf.float32, [None, nrOutputTargets])

yIndices=tf.placeholder(tf.int64, [None, 2])
yValues=tf.placeholder(tf.float32, [None])
yDim=tf.placeholder(tf.int64, [2])
ySparseData=tf.SparseTensor(indices=yIndices, values=yValues, dense_shape=yDim)
ySparseMask=tf.SparseTensor(indices=yIndices, values=tf.ones_like(yValues), dense_shape=yDim)



inputDropout = tf.placeholder(tf.float32)
hiddenDropout = tf.placeholder(tf.float32)
lrGeneral = tf.placeholder(tf.float32)
lrWeight = tf.placeholder(tf.float32)
lrBias = tf.placeholder(tf.float32)
l2PenaltyWeight = tf.placeholder(tf.float32)
l2PenaltyBias = tf.placeholder(tf.float32)
l1PenaltyWeight = tf.placeholder(tf.float32)
l1PenaltyBias = tf.placeholder(tf.float32)
mom = tf.placeholder(tf.float32)
biasInit=tf.placeholder(tf.float32, [nrOutputTargets])
is_training=tf.placeholder(tf.bool)

weightTensors=[]
biasTensors=[]
hidden=[]
hiddenAct=[]
hiddenActMod=[]

with tf.variable_scope('layer_'+str(0)):
  hiddenActl=[]
  hiddenActModl=[]
  if nrDenseFeatures>0.5:
    hiddenActl.append(xDenseData)
    hiddenActModl.append(idropoutFunction(xDenseData, inputDropout, training=is_training))
  if nrSparseFeatures>0.5:
    hiddenActl.append(xSparseData)
    if not (normalizeGlobalSparse or normalizeLocalSparse):
      #dropout: expected is real sparse input data
      hiddenActModl.append(tf.cond(is_training, lambda: tf.sparse_retain(xSparseData, tf.random_uniform([tf.shape(xSparseData.values)[0]])<(1.0-inputDropout))/tf.sqrt(1.0-inputDropout), lambda: xSparseData))
    else:
      #dropout: not possible as input is virtually non-sparse
      xDenseDataFromSparse=tf.sparse_tensor_to_dense(xSparseData, validate_indices=False)+sparseMean
      hiddenActModl.append(idropoutFunction(xDenseDataFromSparse, inputDropout, training=is_training))
  hiddenActInit=hiddenActl
  hiddenActModInit=hiddenActModl
  
  weightTensors.append(None)
  biasTensors.append(None)
  hidden.append(None)
  hiddenAct.append(hiddenActl)
  hiddenActMod.append(hiddenActModl)

layernr=1
with tf.variable_scope('layer_'+str(layernr)):
  wList=[]
  if nrDenseFeatures>0.5:
    WlDense=tf.get_variable("W"+str(layernr)+"_dense", trainable=True, initializer=tf.random_normal([nrDenseFeatures, layerSizes[layernr]], stddev=np.sqrt(initScale/float(layerSizes[layernr-1]))))
    wList.append(WlDense)
  if nrSparseFeatures>0.5:
    WlSparse=tf.get_variable("W"+str(layernr)+"_sparse", trainable=True, initializer=tf.random_normal([nrSparseFeatures, layerSizes[layernr]], stddev=np.sqrt(initScale/float(layerSizes[layernr-1]))))
    wList.append(WlSparse)
    #sparseMeanWSparse=tf.Variable(tf.zeros([1, layerSizes[layernr]]), trainable=False, dtype=tf.float32)
    sparseMeanWSparse=tf.matmul(sparseMean, WlSparse)
  bl=tf.get_variable('b'+str(layernr), shape=[layerSizes[layernr]], trainable=True, initializer=tf.zeros_initializer())
  
  regRaw=l2PenaltyBias*tf.nn.l2_loss(bl)+l1PenaltyBias*tf.reduce_sum(tf.abs(bl))
  if nrDenseFeatures>0.5:
    if nrSparseFeatures>0.5:
      regRaw=regRaw+l2PenaltyWeight*(tf.nn.l2_loss(WlSparse)+tf.nn.l2_loss(WlDense))+l1PenaltyWeight*(tf.reduce_sum(tf.abs(WlSparse))+tf.reduce_sum(tf.abs(WlDense)))
      if type(hiddenActModl[1])==tf.SparseTensor:
        hiddenl=tf.matmul(hiddenActModl[0], WlDense)+tf.sparse_tensor_dense_matmul(hiddenActModl[1], WlSparse)+(bl+sparseMeanWSparse)
      else:
        hiddenl=tf.matmul(hiddenActModl[0], WlDense)+tf.matmul(hiddenActModl[1], WlSparse)+bl
    else:
      regRaw=regRaw+l2PenaltyWeight*tf.nn.l2_loss(WlDense)+l1PenaltyWeight*tf.reduce_sum(tf.abs(WlDense))
      hiddenl=tf.matmul(hiddenActModl[0], WlDense)+bl
  else:
    if nrSparseFeatures>0.5:
      regRaw=regRaw+l2PenaltyWeight*tf.nn.l2_loss(WlSparse)+l1PenaltyWeight*tf.reduce_sum(tf.abs(WlSparse))
      if type(hiddenActModl[0])==tf.SparseTensor:
        hiddenl=tf.sparse_tensor_dense_matmul(hiddenActModl[0], WlSparse)+(bl+sparseMeanWSparse)
      else:
        hiddenl=tf.matmul(hiddenActModl[0], WlSparse)+bl
  hiddenActl=activationFunction(hiddenl)
  hiddenActModl=dropoutFunction(hiddenActl, hiddenDropout, training=is_training)
  
  weightTensors.append(wList)
  biasTensors.append(bl)
  hidden.append(hiddenl)
  hiddenAct.append(hiddenActl)
  hiddenActMod.append(hiddenActModl)

for layernr in range(2, len(layerSizes)-1):
  with tf.variable_scope('layer_'+str(layernr)):
    Wl=tf.get_variable("W"+str(layernr), trainable=True, initializer=tf.random_normal([layerSizes[layernr-1], layerSizes[layernr]], stddev=np.sqrt(initScale/float(layerSizes[layernr-1]))))
    bl=tf.get_variable('b'+str(layernr), shape=[layerSizes[layernr]], trainable=True, initializer=tf.zeros_initializer())
    
    regRaw=regRaw+l2PenaltyWeight*tf.nn.l2_loss(Wl)+l1PenaltyWeight*tf.reduce_sum(tf.abs(Wl))+l2PenaltyBias*tf.nn.l2_loss(bl)+l1PenaltyBias*tf.reduce_sum(tf.abs(bl))
    hiddenl=tf.matmul(hiddenActModl, Wl) + bl
    hiddenActl=activationFunction(hiddenl)
    hiddenActModl=dropoutFunction(hiddenActl, hiddenDropout, training=is_training)
    
    weightTensors.append(Wl)
    biasTensors.append(bl)
    hidden.append(hiddenl)
    hiddenAct.append(hiddenActl)
    hiddenActMod.append(hiddenActModl)

layernr=len(layerSizes)-1
with tf.variable_scope('layer_'+str(layernr)):
  Wl=tf.get_variable("W"+str(layernr), trainable=True, initializer=tf.random_normal([layerSizes[layernr-1], layerSizes[layernr]], stddev=np.sqrt(initScale/float(layerSizes[layernr-1]))))
  bl=tf.get_variable('b'+str(layernr), shape=[layerSizes[layernr]], trainable=True, initializer=tf.zeros_initializer())
  
  regRaw=regRaw+l2PenaltyWeight*tf.nn.l2_loss(Wl)+l1PenaltyWeight*tf.reduce_sum(tf.abs(Wl))+l2PenaltyBias*tf.nn.l2_loss(bl)+l1PenaltyBias*tf.reduce_sum(tf.abs(bl))
  hiddenl=tf.matmul(hiddenActModl, Wl) + bl
  
  weightTensors.append(Wl)
  biasTensors.append(bl)
  hidden.append(hiddenl)
  hiddenAct.append(None)
  hiddenActMod.append(None)



naMat=tf.where(tf.abs(yDenseData) < 0.5, tf.zeros_like(yDenseData), tf.ones_like(yDenseData))
lossRawDense=tf.nn.sigmoid_cross_entropy_with_logits(labels=(yDenseData+1.0)/2.0, logits=hiddenl)*naMat
errOverallDense=tf.reduce_mean(tf.reduce_sum(lossRawDense,1))+regRaw
predNetworkDense=tf.nn.sigmoid(hiddenl)
optimizerDense=tf.train.MomentumOptimizer(momentum=mom, learning_rate=lrGeneral).minimize(errOverallDense)

hiddenlSelected=tf.gather_nd(hiddenl, yIndices)
lossRawSelected=tf.nn.sigmoid_cross_entropy_with_logits(labels=(yValues+1.0)/2.0, logits=hiddenlSelected)
lossRawSparse=tf.SparseTensor(indices=yIndices, values=lossRawSelected, dense_shape=yDim)
errOverallSparse=tf.reduce_mean(tf.sparse_reduce_sum(lossRawSparse, 1))+regRaw
predNetworkSparse=tf.nn.sigmoid(hiddenlSelected)
optimizerSparse=tf.train.MomentumOptimizer(momentum=mom, learning_rate=lrGeneral).minimize(errOverallSparse)

predNetwork=tf.nn.sigmoid(hiddenl)

  
class MyNoOp:
  op=tf.no_op()

init=tf.global_variables_initializer()
biasInitOp=biasTensors[-1].assign(biasInit)
if nrSparseFeatures>0.5:
  #sparseMeanWSparseOp=sparseMeanWSparse.assign(tf.matmul(sparseMean, WlSparse))
  sparseMeanWSparseOp=MyNoOp()
  sparseMeanInitOp=sparseMean.assign(sparseMeanInit)

checkNA=[tf.reduce_any(tf.is_nan(x)) for x in weightTensors[1]+weightTensors[2:]+biasTensors[1:]]
