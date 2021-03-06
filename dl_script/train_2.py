import numpy as np
import tensorflow as tf
import keras
import os
import time
import pickle

from keras.optimizers import Adam
from keras.models import load_model

from keras.callbacks import ModelCheckpoint, CSVLogger

from fully_conv_model_for_lidar_2 import fcn_model
from util_func import *



def list_of_data(data_dir):
	list_of_view = []
	for f in os.listdir(data_dir):
		path = os.path.join(data_dir, f, 'view')
		num_files = len(os.listdir(path))

		views = [os.path.join(path, 'view_'+str(i)+'.npy') for i in range(num_files) ]
		
		list_of_view += views
		
	return list_of_view



def data_generator(list_of_view):
	'''
	input: list_of_lidar, list_of_gtbox
	output: generator of lidar and gtbox
	'''
	n_sample = len(list_of_view)
	next_epoch = True
	
	if len(list_of_view) == 1:
		while True:
			yield list_of_view[0]
	else:

		while True:
			if next_epoch:
				ind = 0
				indices = np.arange(n_sample)
				np.random.shuffle(indices)
				
				yield list_of_view[indices[ind]]
				
				ind = 1
				next_epoch = False
			else:
				yield list_of_view[indices[ind]]
				ind += 1
				if ind >= n_sample:
					next_epoch = True  




def train_batch_generator(list_of_view, batch_size = 32, data_augmentation = True, input_width = 286, output_width = 256, height = 64):

	offset_range = input_width - output_width + 1
	offset = offset_range/2
	ind = 0
	for view_file in data_generator(list_of_view):
		view = np.load(view_file)
		
		if ind == 0:
			batch_sample = np.zeros((batch_size, height, output_width, 2))
			batch_label = np.zeros((batch_size, height, output_width, 8))

		if data_augmentation:
			# Randomly flip the frame
			#flip = np.random.randint(2)
			#if flip:
			#	view = view[:,::-1,:]
			#	view[:,:,-1] = np.pi/2 - view[:,:,-1]
			#flip = 1
			offset = np.random.randint(offset_range)
			#offset = 0
			#lidar, gt_box = augmentation(offset, flip, lidar, gt_box)


		view = view[:,offset:offset+output_width,:]

		batch_sample[ind] = view[:,:,:2]
		batch_label[ind] = view[:,:,2:]

		ind += 1

		if ind == batch_size:
			yield batch_sample, batch_label

			ind = 0

def my_loss(y_true, y_pred):

	seg_true,reg_true = tf.split(y_true, [1, 7], 3)
	seg_pred,reg_pred = tf.split(y_pred, [1, 7], 3)

	#ratio = 20*h*w/tf.reduce_sum(seg_true)
	#weight1 = ((ratio-1)*seg_true + 1)/ratio

	seg_loss = -tf.reduce_mean(tf.multiply(seg_true,tf.log(seg_pred+1e-8)) + tf.multiply(1-seg_true,tf.log(1-seg_pred+1e-8)))
	#seg_loss = -tf.reduce_mean(
	#    tf.multiply(tf.multiply(seg_true,tf.log(seg_pred)) + tf.multiply(1-seg_true,tf.log(1-seg_pred)), weight1))

	diff = tf.reduce_mean(tf.squared_difference(reg_true, reg_pred), axis=3, keep_dims=True)
	reg_loss = tf.reduce_mean(tf.multiply(seg_true,diff))

	#total_loss = reg_loss
	#total_loss = seg_loss
	total_loss = seg_loss + reg_loss
	return total_loss 


if __name__ == '__main__':

	depth_mean = 10.0574
	height_mean = -0.9536
	depth_var = 146.011
	height_var = 0.76245


	mean_tensor, std_tensor = get_mean_std_tensor(depth_mean, height_mean, depth_var, height_var, input_shape = (64,256,2))

	data_dir = './extract_kiti/'

	list_of_view = list_of_data(data_dir)


	#test on just two sample
	#list_of_view = [list_of_view[6831], list_of_view[7279]]
	#list_of_view = [list_of_view[6831]]



	batch_size = 32
	epochs = 100
	augmentation = True
	
	num_frame = len(list_of_view)
	steps_per_epoch = int(num_frame/batch_size)
	
	continue_training = True
	saved_model = './saved_model/model_May_27_185_99.h5'

	if not continue_training:
		model = fcn_model(mean_tensor, std_tensor, input_shape = (64,256,2), summary = True)
		opt = Adam(lr=1e-4)
		#keras.optimizers.Adam(lr=0.001, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=0.0)
		model.compile(optimizer=opt, loss=my_loss)
		
	else:
		from keras.utils.generic_utils import get_custom_objects
		get_custom_objects().update({"my_loss": my_loss})
		
		model = load_model(saved_model)
	#opt = Adam(lr=1e-5)
	# #keras.optimizers.Adam(lr=0.001, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=0.0)
	#model.compile(optimizer=opt, loss=my_loss)
	

	checkpointer = ModelCheckpoint('saved_model/model_May_27_195_{epoch:02d}.h5')
	logger = CSVLogger(filename='saved_model/model_May_27_195.csv')

	print('Start training - batch_size : {0} - num_frame : {1} - steps_per_epoch : {2}'.format(batch_size,num_frame,steps_per_epoch))
	start = time.time()

	model.fit_generator(generator=train_batch_generator(list_of_view, batch_size = batch_size, data_augmentation = augmentation, input_width = 286, output_width = 256, height = 64),
                       steps_per_epoch=steps_per_epoch,
                       epochs=epochs,
                       callbacks=[checkpointer, logger])

	print('End training - during time: {0} minutes'.format( int((time.time() - start)/60) ))
	#model.save("saved_model/model_26_may_test_2_frame.h5")

	# model_json = model.to_json()
	# with open("saved_model/model.json", "w") as json_file:
	# 	json_file.write(model_json)
	# 	# serialize weights to HDF5
	# model.save_weights("saved_model/model.h5")
	# print("Saved model to disk")